"""Sentinel daily orchestrator — runs all stages and escalates to the worst.

    python run_daily.py

Runs six stages in order:
  1. watch  — fetch MOE sources, compare content hashes
  2. scan   — crawl MOE news pages for new AI-related links
  3. audit  — check fact freshness and tool listing validity
  4. build  — generate the static site (refuses if audit fails)
  5. bill   — validate sponsor ledger
  6. data   — collate query logs into structured analysis (Data Bot)

Exit codes:
    0   all stages clean
    1   something needs human attention (stale fact, changed source)
    2   something is broken (dead source, billing error, build refused)
    3   unexpected error (script crash, unparseable output)

A history record is appended to .sentinel_history.jsonl after each run,
so you can see trends over time. Truncated lines (from a killed process)
are skipped on read, not fatal.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from moe import facts as facts_mod
from moe import tools as tools_mod


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / ".sentinel_history.jsonl"
SCAN_STATE = ROOT / ".sentinel_scan_state.json"

#: MOE pages to crawl for new AI-related announcements.
SCAN_URLS = [
    "https://www.moe.gov.sg/news",
    "https://www.moe.gov.sg/news/press-releases",
]

#: Keywords that flag a link as AI-related.
AI_KEYWORDS = ["ai", "artificial intelligence", "chatbot", "chat-bot",
               "generative", "large language", "llm", "gpt"]


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------

def run_json(script: str) -> tuple:
    """Run a Python script and return (parsed_json, exit_code, stderr).

    Returns (None, 3, stderr) if the script cannot be run or its output
    cannot be parsed as JSON. Exit code 3 means 'unexpected error' —
    distinct from the business-logic codes 0/1/2.
    """
    try:
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ROOT),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        return None, 3, str(e)

    # Python returns exit code 2 when it can't open the script file.
    # That's not a business-logic failure — it's "script not found", which
    # maps to our "unexpected error" code 3.
    if result.returncode == 2 and "can't open file" in result.stderr:
        return None, 3, result.stderr.strip()

    if result.returncode != 0 and not result.stdout.strip():
        return None, result.returncode, result.stderr

    try:
        parsed = json.loads(result.stdout.strip())
    except (json.JSONDecodeError, ValueError):
        return None, result.returncode, result.stdout[:200]

    return parsed, result.returncode, result.stderr


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------

def stage_watch() -> dict:
    """Run the URL monitor."""
    parsed, code, err = run_json("run_watch.py")
    if parsed is None:
        return {"stage": "watch", "ok": False, "failed": True, "error": err or "unparseable"}

    return {
        "stage": "watch",
        "ok": code == 0,
        "failed": code == 2,
        "checked": parsed.get("checked", 0),
        "dead": parsed.get("dead", []),
        "changed": parsed.get("changed", []),
    }


def _load_scan_state() -> set[str]:
    """Load previously seen URLs from state file."""
    if SCAN_STATE.exists():
        try:
            data = json.loads(SCAN_STATE.read_text(encoding="utf-8"))
            return set(data.get("urls", []))
        except (json.JSONDecodeError, ValueError):
            return set()
    return set()


def _save_scan_state(urls: set[str]) -> None:
    """Persist seen URLs to state file."""
    SCAN_STATE.write_text(json.dumps({"urls": sorted(urls)}, indent=2), encoding="utf-8")


def _fetch_page(url: str) -> str | None:
    """Fetch a page and return its text, or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Sentinel/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, TimeoutError):
        return None


def _extract_links(html: str, base_url: str) -> set[str]:
    """Extract all absolute moe.gov.sg links from HTML."""
    links = set()
    # Find all href attributes
    for match in re.finditer(r'href=["\']([^"\'>\s]+)["\']', html, re.IGNORECASE):
        href = match.group(1)
        # Resolve relative URLs
        if href.startswith("/"):
            from urllib.parse import urljoin
            href = urljoin(base_url, href)
        # Only keep moe.gov.sg links
        if "moe.gov.sg" in href and href.startswith("https://"):
            # Strip query strings and fragments for dedup
            clean = href.split("?")[0].split("#")[0]
            links.add(clean)
    return links


def _is_ai_related(url: str, text: str) -> bool:
    """Check if a URL or its surrounding text mentions AI."""
    combined = (url + " " + text).lower()
    return any(kw in combined for kw in AI_KEYWORDS)


def stage_scan() -> dict:
    """Crawl MOE news pages for new AI-related links."""
    known = _load_scan_state()
    found: set[str] = set()
    new_links: list[str] = []
    errors: list[str] = []

    for url in SCAN_URLS:
        html = _fetch_page(url)
        if html is None:
            errors.append(url)
            continue
        links = _extract_links(html, url)
        found.update(links)

    # Filter for AI-related links not previously seen
    for link in sorted(found):
        if link not in known and _is_ai_related(link, ""):
            new_links.append(link)

    # Save all found URLs as known
    _save_scan_state(found)

    return {
        "stage": "scan",
        "ok": not new_links,
        "failed": False,
        "new": new_links,
        "total_found": len(found),
        "errors": errors,
    }


def stage_audit() -> dict:
    """Run the fact and tool audit."""
    fact_findings = facts_mod.audit()
    tool_findings = tools_mod.check()
    blocking = [str(f.code) + ": " + f.message[:60] for f in fact_findings + tool_findings if f.severity == "BLOCKING"]

    # Compute the binding deadline: earliest per-fact review date
    deadlines = []
    for f in facts_mod.FACTS:
        src = facts_mod.SOURCES[f.source_key]
        window = src.review_days // 2 if f.watch else src.review_days
        deadlines.append(f.checked_on.toordinal() + window)

    binding_deadline = date.fromordinal(min(deadlines)) if deadlines else date.today()
    days_to_reverify = (binding_deadline - date.today()).days

    return {
        "stage": "audit",
        "ok": not blocking,
        "failed": False,
        "blocking": blocking,
        "facts": len(facts_mod.FACTS),
        "tools": len(tools_mod.TOOLS),
        "verified_days_ago": facts_mod.stale_days(),
        "shortest_window_days": min(
            max(1, facts_mod.SOURCES[f.source_key].review_days // 2) if f.watch
            else facts_mod.SOURCES[f.source_key].review_days
            for f in facts_mod.FACTS
        ),
        "reverify_by": binding_deadline.isoformat(),
        "days_to_reverify": days_to_reverify,
    }


def stage_build() -> dict:
    """Run the site build."""
    from moe import builder
    try:
        messages = builder.build()
        return {
            "stage": "build",
            "ok": True,
            "failed": False,
            "published": True,
            "messages": messages,
        }
    except RuntimeError as e:
        return {
            "stage": "build",
            "ok": False,
            "failed": True,
            "refused": True,
            "published": False,
            "error": str(e),
        }
    except Exception as e:
        return {
            "stage": "build",
            "ok": False,
            "failed": True,
            "refused": False,
            "published": False,
            "error": f"{type(e).__name__}: {e}",
        }


def stage_bill() -> dict:
    """Run the billing check."""
    import run_billing
    try:
        sponsors = run_billing.load()
        problems = run_billing.check_model(sponsors)
        mrr = run_billing.monthly_recurring(sponsors)
        pipe = run_billing.pipeline(sponsors)
        active = sum(1 for s in sponsors if s.status == "active")

        return {
            "stage": "bill",
            "ok": not problems,
            "failed": False,
            "problems": problems,
            "mrr_sgd": mrr,
            "pipeline_sgd": pipe,
            "active_sponsors": active,
            "sponsors": len(sponsors),
        }
    except run_billing.LedgerError as e:
        return {
            "stage": "bill",
            "ok": False,
            "failed": True,
            "problems": [f"Ledger error: {e}"],
            "mrr_sgd": 0,
            "pipeline_sgd": 0,
            "active_sponsors": 0,
            "sponsors": 0,
        }


def stage_data() -> dict:
    """Run the Data Bot — collate query logs into structured analysis."""
    import run_data
    try:
        return run_data.run()
    except Exception as e:
        return {
            "stage": "data",
            "ok": False,
            "failed": True,
            "rows_processed": 0,
            "error": f"{type(e).__name__}: {e}",
        }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def worst_exit(stages: list[dict]) -> int:
    """Return the worst exit code across all stages.

    0 = all clean, 1 = needs human, 2 = broken.
    A broken stage anywhere means exit 2, even if later stages are clean.
    """
    if any(s.get("failed") for s in stages):
        return 2
    if all(s.get("ok") for s in stages):
        return 0
    return 1


def brief(rec: dict) -> str:
    """Format a daily record into a human-readable summary.

    The summary shouts about problems using ALL-CAPS tokens so they stand
    out in a log or email. Each stage gets its own section.
    """
    lines = []
    lines.append("=" * 60)
    lines.append("SENTINEL DAILY REPORT")
    lines.append("=" * 60)
    lines.append(f"  Exit code: {rec.get('exit', '?')}")
    lines.append(f"  Date: {date.today().isoformat()}")
    lines.append("")

    for s in rec.get("stages", []):
        name = s.get("stage", "unknown")
        lines.append(f"  --- {name.upper()} ---")

        if name == "watch":
            checked = s.get("checked", 0)
            dead = s.get("dead", [])
            changed = s.get("changed", [])
            lines.append(f"  Checked: {checked} sources")
            if dead:
                lines.append(f"  DEAD: {', '.join(dead)}")
            if changed:
                lines.append(f"  CHANGED: {', '.join(changed)}")
            if not dead and not changed:
                lines.append("  All sources unchanged.")

        elif name == "scan":
            new = s.get("new", [])
            total = s.get("total_found", 0)
            errors = s.get("errors", [])
            lines.append(f"  Scanned: {len(SCAN_URLS)} pages, {total} links found")
            if new:
                lines.append(f"  NEW: {len(new)} AI-related link(s) not seen before:")
                for link in new:
                    lines.append(f"    - {link}")
            else:
                lines.append("  No new AI-related links.")
            if errors:
                lines.append(f"  ERRORS: {', '.join(errors)}")

        elif name == "audit":
            blocking = s.get("blocking", [])
            facts = s.get("facts", 0)
            tools = s.get("tools", 0)
            days_ago = s.get("verified_days_ago", 0)
            reverify = s.get("reverify_by", "?")
            days_left = s.get("days_to_reverify", 0)
            lines.append(f"  Facts: {facts}, Tools: {tools}")
            lines.append(f"  Last verified: {days_ago} days ago")
            lines.append(f"  Re-verify by: {reverify} ({days_left} days)")
            if blocking:
                lines.append(f"  BLOCKING: {'; '.join(blocking)}")
            else:
                lines.append("  No blocking findings.")

        elif name == "build":
            if s.get("refused"):
                lines.append("  REFUSED — build refused to publish stale claims.")
            elif s.get("published"):
                lines.append("  Published successfully.")
            else:
                lines.append("  Build failed.")
            if s.get("error"):
                lines.append(f"  Error: {s['error']}")

        elif name == "bill":
            mrr = s.get("mrr_sgd", 0)
            pipe = s.get("pipeline_sgd", 0)
            active = s.get("active_sponsors", 0)
            problems = s.get("problems", [])
            lines.append(f"  MRR: S${mrr}, Pipeline: S${pipe}")
            lines.append(f"  Active sponsors: {active}")
            if problems:
                lines.append(f"  ILLEGAL: {'; '.join(problems)}")
            else:
                lines.append("  No billing problems.")

        elif name == "data":
            rows = s.get("rows_processed", 0)
            new_c = s.get("new_combos", 0)
            gaps = s.get("coverage_gaps", 0)
            emerging = s.get("emerging_tools", 0)
            err = s.get("error", "")
            lines.append(f"  Rows processed: {rows}")
            if rows:
                lines.append(f"  New combos: {new_c}, Coverage gaps: {gaps}, Emerging tools: {emerging}")
            if err:
                lines.append(f"  {err}")

        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def read_history() -> list[dict]:
    """Read the history file, skipping truncated lines.

    A process killed mid-write leaves one bad JSON line at the end.
    We skip it rather than crashing, so the viewer always works.
    """
    if not HISTORY.exists():
        return []

    rows = []
    for line in HISTORY.read_text(encoding="utf-8").strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # Truncated line — skip it.
            continue
    return rows


def append_history(rec: dict) -> None:
    """Append one record to the history file."""
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_all() -> dict:
    """Run all six stages and return the aggregated record."""
    stages = [
        stage_watch(),
        stage_scan(),
        stage_audit(),
        stage_build(),
        stage_bill(),
        stage_data(),
    ]

    exit_code = worst_exit(stages)

    return {
        "exit": exit_code,
        "stages": stages,
    }


# ---------------------------------------------------------------------------
# Telegram notification
# ---------------------------------------------------------------------------

def notify_telegram(text: str) -> bool:
    """Send the daily report to Telegram. Returns True on success.

    Reads credentials from environment variables:
        TELEGRAM_BOT_TOKEN  — from @BotFather
        TELEGRAM_CHAT_ID    — your chat ID (from @userinfobot)

    Silently skips if credentials are missing (local dev without Telegram).
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        return False

    # Telegram Bot API has a 4096 char limit per message. Truncate if needed.
    if len(text) > 4000:
        text = text[:4000] + "\n\n... (truncated)"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def main() -> int:
    rec = run_all()
    append_history(rec)

    text = brief(rec)
    print(text)

    # Notify on failure (exit 1 or 2). Clean runs stay silent.
    if rec["exit"] in (1, 2):
        notify_telegram(text)

    return rec["exit"]


if __name__ == "__main__":
    sys.exit(main())
