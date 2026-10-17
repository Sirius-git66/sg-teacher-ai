"""Data Bot — collates raw query logs into structured analysis files.

    python run_data.py

Fetches raw query logs from Netlify Blobs, aggregates them into:
  - data/daily_summary.json   — today's query stats
  - data/coverage_map.json    — all-time per-combo stats
  - data/demand_signals.json  — trends and gaps

Exit codes:
    0   success
    1   no data available (first run, or blob fetch failed)
    2   error

Requires NETLIFY_AUTH_TOKEN env var (GitHub secret for Actions).
Without it, falls back to local cache files if they exist.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
COVERAGE_MAP = DATA_DIR / "coverage_map.json"
DAILY_SUMMARY = DATA_DIR / "daily_summary.json"
DEMAND_SIGNALS = DATA_DIR / "demand_signals.json"

#: Netlify Blobs API endpoint for the queries store.
#: Site ID must be set via NETLIFY_SITE_ID env var.
BLOB_STORE_NAME = "queries"


# ---------------------------------------------------------------------------
# Netlify Blobs fetcher
# ---------------------------------------------------------------------------

def fetch_blob_keys(token: str, site_id: str) -> list[str]:
    """List all keys in the queries blob store."""
    url = f"https://api.netlify.com/api/v1/blobs/{site_id}/store/{BLOB_STORE_NAME}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [k["key"] for k in data.get("blobs", [])]
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []


def fetch_blob(token: str, site_id: str, key: str) -> str:
    """Fetch a single blob's content."""
    url = f"https://api.netlify.com/api/v1/blobs/{site_id}/store/{BLOB_STORE_NAME}/{key}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError):
        return ""


def parse_jsonl(text: str) -> list[dict]:
    """Parse JSONL text into a list of dicts. Skips bad lines."""
    rows = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate(rows: list[dict], prev_coverage: dict) -> dict:
    """Aggregate raw query rows into structured data.

    Returns a dict with keys: daily_summary, coverage_map, demand_signals.
    """
    today = date.today().isoformat()

    # --- Daily summary ---
    total = len(rows)
    by_verdict = Counter(r.get("verdict", "UNKNOWN") for r in rows)
    combo_counter = Counter()
    for r in rows:
        key = f"{r.get('level', '?')}|{r.get('audience', '?')}|{r.get('tool', '?')}"
        combo_counter[key] += 1

    top_combos = [
        {"combo": k, "count": c}
        for k, c in combo_counter.most_common(10)
    ]

    # New combos not in previous coverage map
    new_combos = [k for k in combo_counter if k not in prev_coverage]

    # Combos repeatedly getting MUST_CHECK
    must_check_clusters = [
        {"combo": k, "count": c}
        for k, c in combo_counter.items()
        if rows and all(
            r.get("verdict") == "MUST_CHECK"
            for r in rows
            if f"{r.get('level', '?')}|{r.get('audience', '?')}|{r.get('tool', '?')}" == k
        ) and c >= 3
    ]

    daily_summary = {
        "date": today,
        "total_queries": total,
        "by_verdict": dict(by_verdict),
        "top_combos": top_combos,
        "new_combos": new_combos,
        "must_check_clusters": must_check_clusters,
    }

    # --- Coverage map update ---
    coverage = dict(prev_coverage)
    for r in rows:
        key = f"{r.get('level', '?')}|{r.get('audience', '?')}|{r.get('tool', '?')}"
        verdict = r.get("verdict", "UNKNOWN")
        ts = r.get("ts", "")
        if key not in coverage:
            coverage[key] = {
                "count": 0,
                "verdict": verdict,
                "first_seen": ts[:10] if ts else today,
                "last_seen": ts[:10] if ts else today,
                "trend": "new",
            }
        coverage[key]["count"] += 1
        coverage[key]["last_seen"] = ts[:10] if ts else today
        coverage[key]["verdict"] = verdict  # latest verdict

    # Compute trends (compare count to previous)
    # Simple heuristic: if count grew >10% since last run, trend is "up"
    # This is approximate since we don't store per-run counts
    for key in coverage:
        prev_count = prev_coverage.get(key, {}).get("count", 0)
        curr_count = coverage[key]["count"]
        if prev_count == 0:
            coverage[key]["trend"] = "new"
        elif curr_count > prev_count * 1.1:
            coverage[key]["trend"] = "up"
        elif curr_count < prev_count * 0.9:
            coverage[key]["trend"] = "down"
        else:
            coverage[key]["trend"] = "stable"

    # --- Demand signals ---
    # Trending tools: tools with most queries today
    tool_counter = Counter(r.get("tool", "?") for r in rows)
    trending_tools = [
        {"tool": t, "count": c}
        for t, c in tool_counter.most_common(5)
    ]

    # Coverage gaps: high-demand combos with MUST_CHECK verdict
    coverage_gaps = [
        {"combo": k, "count": v["count"], "verdict": v["verdict"]}
        for k, v in coverage.items()
        if v["verdict"] == "MUST_CHECK" and v["count"] >= 5
    ]
    coverage_gaps.sort(key=lambda x: x["count"], reverse=True)

    # Emerging tools: tools not in the official registry
    # (We check against moe/tools.py for official tools)
    try:
        from moe import tools as tools_mod
        known_tools = set(t.key for t in tools_mod.TOOLS)
        emerging_tools = [
            {"tool": t, "count": c}
            for t, c in tool_counter.items()
            if t not in known_tools
        ]
    except ImportError:
        emerging_tools = []

    demand_signals = {
        "date": today,
        "trending_tools": trending_tools,
        "coverage_gaps": coverage_gaps[:10],
        "emerging_tools": emerging_tools,
    }

    return {
        "daily_summary": daily_summary,
        "coverage_map": coverage,
        "demand_signals": demand_signals,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> dict:
    """Run the Data Bot. Returns a result dict."""
    DATA_DIR.mkdir(exist_ok=True)

    # Load previous coverage map (if exists)
    prev_coverage = {}
    if COVERAGE_MAP.exists():
        try:
            prev_coverage = json.loads(COVERAGE_MAP.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            prev_coverage = {}

    # Fetch raw logs
    token = os.environ.get("NETLIFY_AUTH_TOKEN", "")
    site_id = os.environ.get("NETLIFY_SITE_ID", "")

    all_rows = []

    if token and site_id:
        # Fetch from Netlify Blobs API
        keys = fetch_blob_keys(token, site_id)
        for key in keys:
            content = fetch_blob(token, site_id, key)
            all_rows.extend(parse_jsonl(content))
    else:
        # No token — check for local cache (development mode)
        cache_file = DATA_DIR / "raw_queries_cache.jsonl"
        if cache_file.exists():
            content = cache_file.read_text(encoding="utf-8")
            all_rows = parse_jsonl(content)

    if not all_rows:
        return {
            "stage": "data",
            "ok": False,
            "failed": False,
            "rows_processed": 0,
            "error": "No query data available (set NETLIFY_AUTH_TOKEN and NETLIFY_SITE_ID)",
        }

    # Aggregate
    result = aggregate(all_rows, prev_coverage)

    # Write output files
    DAILY_SUMMARY.write_text(
        json.dumps(result["daily_summary"], indent=2), encoding="utf-8"
    )
    COVERAGE_MAP.write_text(
        json.dumps(result["coverage_map"], indent=2), encoding="utf-8"
    )
    DEMAND_SIGNALS.write_text(
        json.dumps(result["demand_signals"], indent=2), encoding="utf-8"
    )

    return {
        "stage": "data",
        "ok": True,
        "failed": False,
        "rows_processed": len(all_rows),
        "new_combos": len(result["daily_summary"]["new_combos"]),
        "coverage_gaps": len(result["demand_signals"]["coverage_gaps"]),
        "emerging_tools": len(result["demand_signals"]["emerging_tools"]),
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2))

    if result.get("failed"):
        return 2
    if not result.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
