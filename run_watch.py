"""Sentinel — source URL monitor.

Fetches each MOE source URL, strips HTML to plain text, computes a content
hash, and compares against the hash stored from the last run. Reports which
sources are CLEAN (unchanged), CHANGED (content differs), or DEAD (unreachable).

    python run_watch.py

Exit codes:
    0   all sources clean
    1   one or more sources changed (human review needed)
    2   one or more sources unreachable (broken)

Output: JSON to stdout with keys: checked, dead, changed, hashes.
State is persisted in .sentinel_state.json so the next run can compare.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from moe import facts as facts_mod


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / ".sentinel_state.json"

#: Seconds to wait before giving up on a source URL. MOE pages are usually
#: fast; anything over 15s is either a network problem or the page is gone.
TIMEOUT = 15


# ---------------------------------------------------------------------------
# HTML stripping — pure functions, no network, fully testable offline
# ---------------------------------------------------------------------------

def strip_html(raw: bytes) -> str:
    """Strip HTML tags and normalise whitespace, returning plain text.

    Script and style blocks are removed entirely — their content is code,
    not human-readable text, and a changed script tag should not trigger
    a content-change alert. Whitespace is collapsed so that reformatting
    (extra spaces, newlines) does not read as a content change.
    """
    text = raw.decode("utf-8", errors="replace")

    # Remove script and style blocks entirely, including their content.
    # A regex is sufficient here: we are not parsing, we are discarding.
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove all remaining tags.
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities that matter for content comparison.
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')

    # Collapse whitespace: runs of spaces/tabs/newlines become a single space.
    # This is what makes formatting-only changes invisible to the hasher.
    text = re.sub(r"\s+", " ", text).strip()

    return text


def digest_of(raw: bytes) -> str:
    """SHA-256 hex digest of the stripped text content.

    Two HTML documents with the same visible text produce the same digest,
    regardless of tag structure or whitespace formatting.
    """
    text = strip_html(raw)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch(url: str) -> bytes | None:
    """Fetch a URL and return the raw bytes, or None if unreachable.

    A 404, DNS failure, timeout, or SSL error all return None. The caller
    decides whether that means DEAD or something else.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Sentinel/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
        return None


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def load_state() -> dict[str, str]:
    """Load the previous run's content hashes. Returns {} on first run."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def save_state(hashes: dict[str, str]) -> None:
    """Persist content hashes for the next run."""
    STATE_FILE.write_text(json.dumps(hashes, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------

def check() -> dict:
    """Run the full watch check. Returns a result dict.

    The dict has keys:
        checked  — number of sources checked
        dead     — list of source keys that were unreachable
        changed  — list of source keys whose content hash differs
        hashes   — the new hash map (for persistence)
    """
    prev = load_state()
    current: dict[str, str] = {}
    dead: list[str] = []
    changed: list[str] = []

    for key, source in facts_mod.SOURCES.items():
        raw = fetch(source.url)
        if raw is None:
            dead.append(key)
            # Keep the old hash so a transient failure doesn't look like a
            # content change when the source comes back.
            if key in prev:
                current[key] = prev[key]
            continue

        h = digest_of(raw)
        current[key] = h

        if key in prev and prev[key] != h:
            changed.append(key)

    save_state(current)

    return {
        "checked": len(facts_mod.SOURCES),
        "dead": dead,
        "changed": changed,
        "hashes": current,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    result = check()

    print(json.dumps(result, indent=2))

    if result["dead"]:
        return 2
    if result["changed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
