"""Brain Bot — analyzes data and drafts policy updates for approval.

    python run_brain.py

Reads:
  - data/daily_summary.json      (query trends)
  - data/coverage_map.json       (all-time stats)
  - data/demand_signals.json     (gaps, emerging tools)
  - Sentinel scan results        (new MOE content)
  - facts.py, tools.py           (current registry)

Outputs:
  - drafts/proposals.json        (structured change proposals)
  - drafts/history.jsonl         (decision log)

Requires OPENAI_API_KEY env var.
Without it, returns a no-data result (doesn't fail).

Exit codes:
    0   success (proposals generated or no data to analyze)
    1   no data available
    2   error
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DRAFTS_DIR = ROOT / "drafts"
PROPOSALS = DRAFTS_DIR / "proposals.json"
HISTORY = DRAFTS_DIR / "history.jsonl"

# Data files from Data Bot
DAILY_SUMMARY = DATA_DIR / "daily_summary.json"
COVERAGE_MAP = DATA_DIR / "coverage_map.json"
DEMAND_SIGNALS = DATA_DIR / "demand_signals.json"


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    """Load a JSON file, returning empty dict if missing or corrupt."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return {}


def load_registry() -> dict:
    """Load current facts and tools from the registry."""
    try:
        from moe import facts as facts_mod
        from moe import tools as tools_mod
        
        facts_summary = {
            "count": len(facts_mod.FACTS),
            "stale_days": facts_mod.stale_days(),
            "sources": len(facts_mod.SOURCES),
        }
        
        tools_summary = {
            "count": len(tools_mod.TOOLS),
            "tools": [
                {"key": t.key, "name": t.name, "vendor": t.vendor}
                for t in tools_mod.TOOLS
            ],
        }
        
        return {"facts": facts_summary, "tools": tools_summary}
    except ImportError:
        return {"facts": {}, "tools": {}}


# ---------------------------------------------------------------------------
# OpenAI integration
# ---------------------------------------------------------------------------

def call_openai(prompt: str, system: str = "") -> str:
    """Call OpenAI API and return the response text.
    
    Uses GPT-4o-mini for cost efficiency (~$0.01 per call).
    Returns empty string on failure.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return ""
    
    try:
        import urllib.request
        
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system or "You are Brain Bot, an AI compliance analyst for Singapore teachers. You analyze MOE policy data and draft clear, actionable updates."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1000,
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    
    except Exception as e:
        print(f"OpenAI API error: {e}", file=sys.stderr)
        return ""


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def build_prompt(data: dict, registry: dict) -> str:
    """Build the prompt for OpenAI."""
    today = date.today().isoformat()
    
    # Summarize the data
    summary = data.get("daily_summary", {})
    signals = data.get("demand_signals", {})
    coverage = data.get("coverage_map", {})
    
    prompt = f"""Today is {today}.

CURRENT REGISTRY:
- Facts: {registry.get('facts', {}).get('count', 0)} total, last verified {registry.get('facts', {}).get('stale_days', '?')} days ago
- Tools: {registry.get('tools', {}).get('count', 0)} registered

QUERY DATA (last 24h):
- Total queries: {summary.get('total_queries', 0)}
- Top combos: {json.dumps(summary.get('top_combos', [])[:5])}
- New combos: {len(summary.get('new_combos', []))}
- MUST_CHECK clusters: {json.dumps(summary.get('must_check_clusters', [])[:3])}

DEMAND SIGNALS:
- Trending tools: {json.dumps(signals.get('trending_tools', [])[:5])}
- Coverage gaps (high demand + MUST_CHECK): {json.dumps(signals.get('coverage_gaps', [])[:5])}
- Emerging tools (not in registry): {json.dumps(signals.get('emerging_tools', [])[:5])}

COVERAGE MAP:
- Total combos tracked: {len(coverage)}
- Combos with trend "up": {sum(1 for v in coverage.values() if v.get('trend') == 'up')}
- Combos with verdict MUST_CHECK: {sum(1 for v in coverage.values() if v.get('verdict') == 'MUST_CHECK')}

TASK:
Analyze this data and propose specific, actionable updates. Focus on:
1. Coverage gaps — combos teachers ask about repeatedly but get MUST_CHECK
2. Emerging tools — tools appearing in queries but not in registry
3. Stale facts — if verified_days_ago is high, flag for re-verification
4. Trending tools — if a tool is trending, ensure its fact is current

Return a JSON object with this structure:
{{
  "proposals": [
    {{
      "type": "new_tool" | "fact_update" | "verdict_change",
      "priority": "high" | "medium" | "low",
      "title": "Brief title",
      "rationale": "Why this change is needed",
      "details": "Specific change to make"
    }}
  ],
  "summary": "One-paragraph summary of findings"
}}

If no changes are needed, return {{"proposals": [], "summary": "No urgent changes needed."}}
"""
    return prompt


def analyze(data: dict, registry: dict) -> dict:
    """Run the analysis via OpenAI and parse the response."""
    prompt = build_prompt(data, registry)
    response = call_openai(prompt)
    
    if not response:
        return {"proposals": [], "summary": "OpenAI API unavailable or no response."}
    
    # Try to parse JSON from the response
    # OpenAI might wrap it in markdown code blocks, so strip those
    response = response.strip()
    if response.startswith("```"):
        # Remove markdown code blocks
        lines = response.split("\n")
        response = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # If parsing fails, return the raw response as a summary
        return {
            "proposals": [],
            "summary": f"LLM response (unparseable): {response[:200]}",
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> dict:
    """Run the Brain Bot. Returns a result dict."""
    DRAFTS_DIR.mkdir(exist_ok=True)
    
    # Load data
    data = {
        "daily_summary": load_json(DAILY_SUMMARY),
        "coverage_map": load_json(COVERAGE_MAP),
        "demand_signals": load_json(DEMAND_SIGNALS),
    }
    
    registry = load_registry()
    
    # Check if there's any data to analyze
    total_queries = data["daily_summary"].get("total_queries", 0)
    if total_queries == 0 and not data["demand_signals"].get("emerging_tools"):
        return {
            "stage": "brain",
            "ok": False,
            "failed": False,
            "proposals": 0,
            "error": "No query data to analyze yet",
        }
    
    # Analyze
    result = analyze(data, registry)
    
    # Write proposals
    proposals = {
        "date": date.today().isoformat(),
        "proposals": result.get("proposals", []),
        "summary": result.get("summary", ""),
    }
    
    PROPOSALS.write_text(
        json.dumps(proposals, indent=2), encoding="utf-8"
    )
    
    # Append to history
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "date": date.today().isoformat(),
            "proposals_count": len(proposals["proposals"]),
            "summary": proposals["summary"],
        }) + "\n")
    
    return {
        "stage": "brain",
        "ok": True,
        "failed": False,
        "proposals": len(proposals["proposals"]),
        "high_priority": sum(1 for p in proposals["proposals"] if p.get("priority") == "high"),
        "summary": proposals["summary"][:100],
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
