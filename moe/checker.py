"""Scenario checker — pre-computed verdicts for every level x audience x tool.

The checker answers one question: "Can I use tool X at level Y with audience Z
under MOE rules?" Every answer is traced to named fact keys in the registry.
No rule lives in this module's output — the JavaScript that renders answers
on the site performs lookups only, never verdict logic.

Verdicts:
    NOT_ALLOWED   — MOE rules bar this combination (e.g. chatbots at P1-3)
    MUST_CHECK    — requires school approval, parental consent, or both
    SUPERVISED    — permitted under teacher supervision with conditions
    ALLOWED       — permitted (teacher-only use with no student data)
    UNKNOWN       — tool not in registry; refusal, not a guess
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from . import facts as facts_mod
from . import tools as tools_mod


LEVELS = {"p1_3", "p4_6", "secondary", "jc"}
AUDIENCES = {"teacher", "student"}


@dataclass(frozen=True)
class Answer:
    """One pre-vetted answer.

    `reasons`, `conditions`, and `evidence` are always tuples — never bare
    strings. A bare string iterated character-by-character was a real bug
    that shipped once; the coercion below ensures it cannot happen again.
    """

    verdict: str
    h: str
    reasons: Tuple[str, ...] = ()
    conditions: Tuple[str, ...] = ()
    evidence: Tuple[str, ...] = ()
    escalate: str = ""

    def __post_init__(self):
        for fname in ("reasons", "conditions", "evidence"):
            val = getattr(self, fname)
            if isinstance(val, str):
                object.__setattr__(self, fname, (val,))


# ---------------------------------------------------------------------------
# Universal conditions that appear on every non-UNKNOWN answer
# ---------------------------------------------------------------------------

NO_PII = (
    "Do not paste student names, class lists, NRICs, or photographs "
    "of students into any AI tool. MOE requires that input data contains "
    "no personal identifiable information."
)

NO_PII_TEACHER = (
    "For your own work: do not paste student names, class lists, NRICs, "
    "photographs of students, or marked scripts containing names."
)


def answer(level: str, audience: str, tool_key: str) -> Answer:
    """Return the pre-vetted answer for one scenario.

    The five verdicts form a ladder. NOT_ALLOWED is the most restrictive,
    ALLOWED the least. UNKNOWN is a refusal that sits outside the ladder —
    it means we have no data, not that anything is permitted or barred.
    """
    tool = tools_mod.TOOLS_BY_KEY.get(tool_key)

    # --- unknown tool: refuse, do not guess ---
    if tool is None:
        return Answer(
            verdict="UNKNOWN",
            h="We have not reviewed this tool",
            reasons=(
                "This tool is not in our registry. We cannot give you a "
                "verdict we have not verified.",
            ),
            conditions=(
                NO_PII,
                "Parental consent is required where external AI tools are "
                "introduced. Without consent, students cannot use them.",
            ),
            evidence=(),
            escalate=(
                "Ask your school's AI coordinator or check MOE's official "
                "guidance before proceeding."
            ),
        )

    # --- unknown level or audience ---
    if level not in LEVELS or audience not in AUDIENCES:
        return Answer(
            verdict="UNKNOWN",
            h="We cannot answer that combination",
            reasons=("We do not have pre-vetted guidance for that selection.",),
            conditions=(),
            evidence=(),
            escalate="Check MOE's official guidance or ask your school's AI coordinator.",
        )

    is_official = tool.official

    # ===================================================================
    # TEACHER-ONLY USE — the lowest-risk path
    # ===================================================================
    if audience == "teacher":
        if is_official:
            return Answer(
                verdict="ALLOWED",
                h="Yes, for your own work",
                reasons=(
                    f"{tool.name} is an official MOE tool built into the "
                    f"Student Learning Space. Teachers may use it freely.",
                ),
                conditions=(NO_PII_TEACHER,),
                evidence=("moe_commitments", "sls_moe_built_with_teachers"),
            )
        else:
            return Answer(
                verdict="ALLOWED",
                h="Yes, for your own work",
                reasons=(
                    "Teacher-only use of commercial AI tools is the lowest-risk "
                    "and most defensible use, as long as no student data is involved.",
                ),
                conditions=(
                    NO_PII_TEACHER,
                    "Do not use student data in any form — no names, no scripts, "
                    "no photographs of student work.",
                ),
                evidence=("commercial_no_pii",),
            )

    # ===================================================================
    # STUDENT USE — level-dependent, tool-dependent
    # ===================================================================

    # P1-3: no student may use any AI tool directly
    if level == "p1_3":
        return Answer(
            verdict="NOT_ALLOWED",
            h="Not at this level",
            reasons=(
                "MOE is explicit: Primary 1 to 3 is hands-on and print-first. "
                "Students are introduced to what AI is and how it appears in "
                "daily life, but schools will not assign any work that requires "
                "them to use AI directly. Students will not be tasked to use "
                "chatbots.",
            ),
            conditions=(
                "AI may be used by teachers to provide customised feedback, "
                "but students themselves are not tasked to use any AI tool.",
            ),
            evidence=("p1_p3_rule",),
            escalate=(
                "If your school is considering an exception, check with your "
                "school's AI coordinator and MOE's official guidance first."
            ),
        )

    # Official SLS tools at P4-6, Secondary, JC: supervised use
    if is_official:
        conditions = ["Supervised use by a teacher."]
        evidence_keys = ["sls_ai_features_exist", "p4_p6_rule"]

        if level == "p4_6":
            conditions.append(
                "Students should complete the Basic Module on AI and "
                "AI-enabled features in SLS before using this tool."
            )

        if level in ("secondary", "jc"):
            conditions.append(
                "Students must state where they have used AI and cite "
                "their sources. Passing off AI-generated content as their "
                "own carries consequences for academic dishonesty."
            )
            evidence_keys.append("disclosure_rule")
            escalate = (
                "National examinations prohibit AI use. Ensure students "
                "understand the boundary between permitted classroom use "
                "and exam conditions."
            )

        if level == "jc":
            conditions.append(
                "National examinations are proctored and AI use is "
                "prohibited. Ensure students understand the boundary "
                "between permitted classroom use and exam conditions."
            )
            evidence_keys.append("exams_prohibited")

        return Answer(
            verdict="SUPERVISED",
            h="Yes, with supervision",
            reasons=(
                f"{tool.name} is an official MOE tool with in-built safety "
                f"guardrails, designed for education.",
            ),
            conditions=tuple(conditions),
            evidence=tuple(evidence_keys),
            escalate=escalate if level in ("secondary", "jc") else "",
        )

    # Commercial tools with students: never cleared outright
    # At every level, the answer is MUST_CHECK
    conditions = [
        "Only with your school's explicit approval. MOE requires schools "
        "to check that commercial-off-the-shelf tools comply with data "
        "management guidelines.",
        "Input must contain no personal identifiable information. This is "
        "a MOE requirement stated in Parliament on 6 May 2026.",
        "Parental consent is required where external tools are introduced. "
        "Without consent, students cannot use them.",
    ]
    evidence_keys = ["commercial_no_pii", "parental_consent"]

    if level == "p4_6":
        conditions.append(
            "Students in Primary 4 to 6 may only use AI tools specifically "
            "designed for education, under teacher supervision. A general-purpose "
            "chatbot is not 'specifically designed for education'."
        )
        evidence_keys.append("p4_p6_rule")

    if level in ("secondary", "jc"):
        conditions.append(
            "Students must state where they have used AI and cite their "
            "sources. Passing off AI-generated content as their own carries "
            "consequences for academic dishonesty."
        )
        evidence_keys.append("disclosure_rule")

    if level == "jc":
        conditions.append(
            "National examinations are proctored and AI use is prohibited."
        )
        evidence_keys.append("exams_prohibited")

    return Answer(
        verdict="MUST_CHECK",
        h="Only with your school's approval",
        reasons=(
            "This is a commercial tool, not built by MOE. We cannot verify "
            "its data handling, training terms, or age gating. MOE requires "
            "schools to approve external tools before students use them.",
        ),
        conditions=tuple(conditions),
        evidence=tuple(evidence_keys),
    )


def citations_for(a: Answer) -> list[tuple[str, str, str]]:
    """Resolve an answer's evidence keys into (publisher, url, quote) triples.

    Returns one entry per evidence key. Each quote is verbatim from the
    source — never paraphrased. A teacher clicking through can verify
    every claim in seconds.
    """
    out = []
    for key in a.evidence:
        fact = facts_mod.FACTS_BY_KEY.get(key)
        if fact is None:
            continue
        source = facts_mod.SOURCES.get(fact.source_key)
        if source is None:
            continue
        out.append((source.publisher, source.url, fact.quote))
    return out


def all_tool_options() -> list[tuple[str, str, str, str]]:
    """Every tool as (tool_key, level, audience, tool_name) for the GUI.

    The site offers each tool at each level for each audience. The checker
    then looks up the pre-vetted answer. Tools are grouped into official
    and commercial for display purposes.
    """
    return [
        (t.key, level, audience, t.name)
        for t in tools_mod.TOOLS
        for level in sorted(LEVELS)
        for audience in sorted(AUDIENCES)
    ]


def checker_payload() -> dict:
    """Build the full JSON-serialisable payload for checker-data.js.

    This is what the JavaScript reads. Every key is "level|audience|tool_key".
    Every value contains the verdict, heading, conditions, evidence keys,
    resolved citations, and escalation text.

    The JS performs lookups only. No verdict logic lives in the JavaScript.
    """
    answers = {}
    for level in LEVELS:
        for audience in AUDIENCES:
            for t in tools_mod.TOOLS:
                key = f"{level}|{audience}|{t.key}"
                a = answer(level, audience, t.key)
                cites = citations_for(a)
                answers[key] = {
                    "v": a.verdict,
                    "h": a.h,
                    "r": list(a.reasons),
                    "c": list(a.conditions),
                    "e": list(a.evidence),
                    "s": [[pub, url, q] for pub, url, q in cites],
                    "esc": a.escalate,
                }
    return {"a": answers}
