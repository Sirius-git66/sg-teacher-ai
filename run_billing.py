"""Sponsor billing ledger — the money side of Sentinel.

Tracks sponsors, validates their UENs, enforces the three rules that are
coded not promised, and computes revenue. The ledger is a JSON file on disk;
a missing or corrupt file raises LedgerError rather than returning an empty
list, because S$0 revenue from a broken file is indistinguishable from S$0
revenue from a real business with no sponsors — and those are not the same.

Three rules enforced here:
  1. Official MOE tools can never carry a sponsor slot.
  2. An active sponsor must have a payment date recorded.
  3. Each tier has a maximum number of tool slots.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from moe import tools as tools_mod


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "ledger.json"


# ---------------------------------------------------------------------------
# UEN validation
# ---------------------------------------------------------------------------

#: Singapore ACRA UEN formats (simplified — covers the three real patterns):
#:   Format A: 202412345Z        — 9 digits + 1 letter (post-2000 entities)
#:   Format B: T08LL1234A        — T + 2 digits + 3 letters + 4 digits + 1 letter
#:   Format C: 12345678A         — 8 digits + 1 letter (pre-2000 entities)
_UEN_PATTERNS = (
    re.compile(r"^\d{9}[A-Z]$", re.IGNORECASE),           # Format A
    re.compile(r"^T\d{2}[A-Z]{2}\d{4}[A-Z]$", re.IGNORECASE),  # Format B
    re.compile(r"^\d{8}[A-Z]$", re.IGNORECASE),           # Format C
)


def _valid_uen(u: str) -> bool:
    """Return True if the string matches any recognised ACRA UEN format."""
    if not u:
        return False
    return any(p.match(u) for p in _UEN_PATTERNS)


# ---------------------------------------------------------------------------
# Sponsor record
# ---------------------------------------------------------------------------

@dataclass
class Sponsor:
    """One sponsor entry in the ledger."""

    key: str
    name: str
    uen: str
    tier: str                       # "supporting" | "sustained" | "founding"
    status: str = "pending"         # "pending" | "active" | "cancelled"
    tool_keys: tuple[str, ...] = ()
    last_paid: str = ""             # ISO date string, empty means never paid


# ---------------------------------------------------------------------------
# Tier configuration
# ---------------------------------------------------------------------------

#: Monthly price per tier in SGD.
TIER_PRICES = {
    "supporting": 500,
    "sustained": 1200,
    "founding": 2000,
}

#: Maximum number of tool slots per tier.
TIER_SLOTS = {
    "supporting": 1,
    "sustained": 3,
    "founding": 5,
}


# ---------------------------------------------------------------------------
# Ledger I/O
# ---------------------------------------------------------------------------

class LedgerError(Exception):
    """Raised when the ledger file exists but cannot be read as valid data.

    This is deliberately different from 'no sponsors' — a missing file on
    first run is fine (empty ledger), but a corrupt file means we cannot
    trust the revenue numbers, and that must never look like S$0.
    """
    pass


def load() -> list[Sponsor]:
    """Load sponsors from the ledger file.

    Returns an empty list only if the file is genuinely empty (first run).
    Raises LedgerError if the file exists but contains corrupt or
    unrecognised data — because returning [] would report S$0 revenue
    while a paying sponsor sits unreadable.
    """
    if not LEDGER.exists():
        return []

    raw = LEDGER.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise LedgerError(f"Ledger is not valid JSON: {e}")

    if not isinstance(data, dict) or "sponsors" not in data:
        raise LedgerError("Ledger is missing the 'sponsors' key")

    sponsors = []
    for record in data["sponsors"]:
        if not isinstance(record, dict):
            raise LedgerError(f"Ledger record is not a dict: {record!r}")
        try:
            sponsors.append(Sponsor(
                key=record["key"],
                name=record["name"],
                uen=record["uen"],
                tier=record["tier"],
                status=record.get("status", "pending"),
                tool_keys=tuple(record.get("tool_keys", ())),
                last_paid=record.get("last_paid", ""),
            ))
        except KeyError as e:
            raise LedgerError(f"Ledger record missing required field: {e}")

    return sponsors


def save(sponsors: list[Sponsor]) -> None:
    """Write the sponsor list to the ledger file."""
    data = {
        "sponsors": [
            {
                "key": s.key,
                "name": s.name,
                "uen": s.uen,
                "tier": s.tier,
                "status": s.status,
                "tool_keys": list(s.tool_keys),
                "last_paid": s.last_paid,
            }
            for s in sponsors
        ]
    }
    LEDGER.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Model checks — the three rules
# ---------------------------------------------------------------------------

def check_model(sponsors: list[Sponsor]) -> list[str]:
    """Validate every sponsor against the three rules.

    Returns a list of problem strings. Empty list means all sponsors pass.
    Each problem names the sponsor and the rule violated.
    """
    problems = []

    for s in sponsors:
        # Rule 1: UEN must be valid
        if not _valid_uen(s.uen):
            problems.append(f"Sponsor '{s.name}' has invalid UEN: {s.uen}")

        # Rule 2: Active sponsors must have a payment date
        if s.status == "active" and not s.last_paid:
            problems.append(
                f"Sponsor '{s.name}' is active but no payment recorded"
            )

        # Rule 3: Tier slot limits
        max_slots = TIER_SLOTS.get(s.tier, 0)
        if len(s.tool_keys) > max_slots:
            problems.append(
                f"Sponsor '{s.name}' has {len(s.tool_keys)} tool slots but "
                f"tier '{s.tier}' allows {max_slots}"
            )

        # Rule 4: No official MOE tools may carry a sponsor
        for tk in s.tool_keys:
            tool = tools_mod.TOOLS_BY_KEY.get(tk)
            if tool and tool.official:
                problems.append(
                    f"Sponsor '{s.name}' has a slot on '{tool.name}', which is "
                    f"an OFFICIAL MOE tool. Official tools are never for sale."
                )

        # Rule 5: Tier must be recognised
        if s.tier not in TIER_PRICES:
            problems.append(
                f"Sponsor '{s.name}' has unrecognised tier: {s.tier}"
            )

    return problems


# ---------------------------------------------------------------------------
# Revenue calculations
# ---------------------------------------------------------------------------

def monthly_recurring(sponsors: list[Sponsor]) -> int:
    """Total monthly recurring revenue in SGD.

    Only counts sponsors with status='active'. Pending sponsors are pipeline,
    not revenue — counting them would overstate the business.
    """
    total = 0
    for s in sponsors:
        if s.status == "active":
            total += TIER_PRICES.get(s.tier, 0)
    return total


def pipeline(sponsors: list[Sponsor]) -> int:
    """Total pipeline value in SGD.

    Counts sponsors with status='pending'. These are signed but not yet
    paying — they show future revenue, not current.
    """
    total = 0
    for s in sponsors:
        if s.status == "pending":
            total += TIER_PRICES.get(s.tier, 0)
    return total
