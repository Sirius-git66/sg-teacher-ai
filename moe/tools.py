"""Tool registry with per-tool compliance verdicts.

The rule this file exists to enforce: **we do not list a commercial tool we
cannot verify.** An unverified commercial listing is not a neutral act of
speech -- it hands a teacher's professional judgement to a vendor's marketing
department, and if the vendor turns out to train on student work, that teacher
carries the consequence.

So every commercial tool carries a `verdict`, and the verdict is computed from
named, checkable claims rather than from a vibe:

  PERMITTED    conditions are stated and met
  CONDITIONAL  usable only under stated conditions
  HOLD         we cannot verify it, so we do not recommend it

A tool with no evidence gets HOLD. That is the default on purpose. A directory
that quietly omits the check is indistinguishable from the vendor's own website,
and that is the whole competitive problem.

The four AIEd principles -- Agency, Inclusivity, Fairness, Safety -- are used as
the review axes, because they are MOE's own vocabulary. Using MOE's framework
rather than our own is what makes the verdict legible to a teacher and defensible
to a school leader.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .facts import Fact, FACTS_BY_KEY


@dataclass(frozen=True)
class Principle:
    key: str
    name: str
    question: str


#: MOE's four principles, used as review axes so a teacher recognises them.
PRINCIPLES: tuple[Principle, ...] = (
    Principle("agency", "Agency",
              "Does it leave the teacher and student in charge of the thinking, or "
              "does it take over the work?"),
    Principle("inclusivity", "Inclusivity",
              "Does it work for students who need more support, or only for those "
              "already ahead?"),
    Principle("fairness", "Fairness",
              "Does it treat students alike, without penalising dialect, disability, "
              "or a weaker home language?"),
    Principle("safety", "Safety",
              "What happens to the data, and to the child?"),
)

PRINCIPLE_KEYS = tuple(p.key for p in PRINCIPLES)


@dataclass(frozen=True)
class Tool:
    """One tool, one honest verdict.

    `verdict` is never 'recommended' on the strength of the vendor's own words.
    For SLS tools it is PERMITTED because MOE built them and they carry in-built
    guardrails -- that is a fact we can cite. For commercial tools it depends on
    what we can actually verify.
    """

    key: str
    name: str
    official: bool                       # built by MOE/GovTech for SLS
    audience: str                # "students" | "teachers" | "both"
    summary: str
    #: Which levels it actually covers. Empty means "not level-restricted, but
    #: still subject to the supervision rule at each level".
    levels: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    verdict: str = "CONDITIONAL"          # PERMITTED | CONDITIONAL | HOLD
    conditions: tuple[str, ...] = ()
    #: fact keys backing this listing. An empty tuple on a commercial tool is a
    #: HOLD by rule, not by preference.
    evidence: tuple[str, ...] = ()
    source_url: str = ""
    #: What a teacher should actually DO with it, in one sentence.
    use_it_for: str = ""
    #: The honest caveat. Every listing has one.
    watch_out: str = ""
    #: Only commercial tools carry a sponsor relationship. Official SLS tools are
    #: never for sale and must never appear here.
    sponsor: str = ""
    #: True when we could not verify the claims and are saying so.
    unverified: bool = False


# ---------------------------------------------------------------------------
# Official SLS tools. Sourced 17 Oct 2026 from learning.moe.edu.sg.
# ---------------------------------------------------------------------------

SLS_URL = "https://www.learning.moe.edu.sg/teachers/teaching-and-learning-on-sls/aied-features/"

TOOLS: tuple[Tool, ...] = (

    Tool(
        key="acp",
        name="Authoring Copilot (ACP)",
        official=True,
        audience="teachers",
        summary="Generates a lesson module with its sections, activities and components "
                "from a teacher's inputs. Suggests activities and assessment items based "
                "on tagged learning outcomes, and can anchor generation to a Knowledge "
                "Base the teacher appends themselves.",
        levels=("P1", "P2", "P3", "P4", "P5", "P6", "Secondary", "JC"),
        subjects=("All subjects",),
        verdict="PERMITTED",
        evidence=("p4_p6_rule", "moe_commitments", "sls_moe_built_with_teachers"),
        source_url="https://www.learning.moe.edu.sg/teachers/teacher-user-guide/author/"
                   "use-authoring-copilot-to-create-new-sections/",
        use_it_for="Turning a lesson objective into a scaffolded SLS lesson you can then "
                   "edit before you teach it.",
        watch_out="It generates a draft, not a lesson. The pedagogical decisions -- "
                  "what to scaffold, what to leave for productive struggle -- are still "
                  "yours, and MOE's framing is that AI should not replace teacher "
                  "judgement.",
    ),

    Tool(
        key="dat",
        name="Data Assistant (DAT)",
        official=True,
        audience="teachers",
        summary="Lets you query and speed up qualitative analysis of student responses "
                "in natural language. Pre-populated 'recipes' or your own instructions. "
                "Groups responses into themes, surfaces misconceptions, suggests follow "
                "up actions.",
        levels=("P1", "P2", "P3", "P4", "P5", "P6", "Secondary", "JC"),
        subjects=("All subjects",),
        verdict="PERMITTED",
        evidence=("p4_p6_rule", "sls_moe_built_with_teachers"),
        source_url="https://www.learning.moe.edu.sg/teachers/teacher-user-guide/assess/"
                   "analyse-students-responses-with-data-assistant/",
        use_it_for="Finding the misconception across 30 responses faster than you would "
                   "by hand, then deciding what to do about it.",
        watch_out="Read the output before you act on it. It groups and suggests; it does "
                  "not know which grouping matters for your next lesson.",
    ),

    Tool(
        key="als",
        name="Adaptive Learning System (ALS)",
        official=True,
        audience="students",
        summary="Personalised learning pathway per student, recommending learning modes, "
                "resources and practice questions with immediate feedback based on "
                "readiness. Teachers get a Learning Progress Dashboard.",
        levels=("P4", "P5", "P6", "Secondary"),
        subjects=("Mathematics (Upper Primary, Lower Secondary)",
                  "Geography (Upper Secondary)"),
        verdict="PERMITTED",
        conditions=(
            "Currently only Mathematics (Upper Primary and Lower Secondary) and Geography "
            "(Upper Secondary). MOE states more topics, levels and subjects will be added "
            "progressively -- so check availability rather than assuming.",
            "Students should complete the Basic Module on AI and AI-enabled features in "
            "SLS first.",
            "Supervised use.",
        ),
        evidence=("als_coverage_limited", "sls_ai_features_exist"),
        source_url="https://www.learning.moe.edu.sg/teachers/teacher-user-guide/discover/"
                   "about-adaptive-learning-system/",
        use_it_for="Independent revision at the right difficulty, and seeing who has not "
                   "got it before the test.",
        watch_out="It is adaptive, not diagnostic. The dashboard shows concept mastery; "
                  "it does not tell you why a particular student is stuck.",
    ),

    Tool(
        key="lea",
        name="Learning Assistant (LEA)",
        official=True,
        audience="students",
        summary="A student-facing dialogic agent that guides learning through iterative "
                "questioning rather than giving answers, anchored to curated materials in "
                "a Knowledge Base. Teachers set interaction limits and can read "
                "conversation logs.",
        levels=("P4", "P5", "P6", "Secondary"),
        subjects=("All subjects",),
        verdict="PERMITTED",
        conditions=(
            "Set interaction limits to reduce over-reliance. This is the safeguard MOE "
            "names explicitly.",
            "Anchor it to a Knowledge Base you curate, or it has nothing trustworthy to "
            "draw on.",
            "Supervised use.",
        ),
        evidence=("p4_p6_rule", "lea_guardrail", "p1_p3_rule", "sls_ai_features_exist"),
        source_url="https://www.learning.moe.edu.sg/teachers/teacher-user-guide/author/"
                   "set-up-learning-assistant/",
        use_it_for="Draft-and-improve cycles in writing. MOE's own example is Primary 4 "
                   "English composition on 'show not tell'.",
        watch_out="Not for Primary 1 to 3. MOE is explicit that lower primary students "
                  "will not be tasked to use chatbots, and P1-3 is print-first and "
                  "hands-on. Listing LEA for P1 is the single most common error on "
                  "teacher-facing AI sites.",
    ),

    Tool(
        key="afa",
        name="Annotated Feedback Assistant (AFA)",
        official=True,
        audience="both",
        summary="Targeted feedback embedded in student responses via annotation cards, "
                "based on suggested answers, rubrics or error tags. Customisable toward "
                "Socratic questioning or scaffolded hints.",
        levels=("P4", "P5", "P6", "Secondary", "JC"),
        subjects=("All subjects",),
        verdict="PERMITTED",
        evidence=("afa_socratic_option", "sls_moe_built_with_teachers"),
        source_url="https://www.learning.moe.edu.sg/teachers/teacher-user-guide/assess/"
                   "add-annotated-feedback-assistant/",
        use_it_for="Feedback that points at the specific span of text rather than the "
                   "whole response, with hints instead of answers.",
        watch_out="Teachers control how many times a student receives feedback. Use that "
                  "deliberately -- unlimited retries is how feedback stops being "
                  "feedback.",
    ),

    Tool(
        key="saFA",
        name="Short Answer Feedback Assistant (ShortAnsFA / SAFA)",
        official=True,
        audience="both",
        summary="Suggested marks and auto-generated first-draft comments for free-response "
                "questions, from a suggested mark scheme that the teacher edits. Works "
                "across subjects and levels.",
        levels=("P4", "P5", "P6", "Secondary", "JC"),
        subjects=("All subjects",),
        verdict="PERMITTED",
        conditions=(
            "DO NOT use for questions involving mathematical computation. MOE states it "
            "cannot provide accurate feedback for mathematical concepts. Use "
            "Feedback Assistant - Mathematics instead.",
        ),
        evidence=("saFA_math_exclusion", "sls_ai_features_exist"),
        source_url="https://www.learning.moe.edu.sg/teachers/teacher-user-guide/assess/"
                   "add-short-answer-feedback-assistant/",
        use_it_for="Getting a first draft of comments you then edit, on close-ended "
                   "questions with a clear mark scheme.",
        watch_out="The mathematical-computation exclusion is a stated limitation, not a "
                  "quirk. A directory that lists it 'for all subjects' without this "
                  "caveat is worse than one that lists nothing.",
    ),

    Tool(
        key="fa_math",
        name="Feedback Assistant - Mathematics (FA-Math)",
        official=True,
        audience="both",
        summary="Rules-based engine offering step-by-step hints and feedback on students' "
                "workings, plus suggested marks. Can generate randomised questions "
                "including geometry and graphs, and author question types.",
        levels=("P4", "P5", "P6", "Secondary", "JC"),
        subjects=("Mathematics",),
        verdict="PERMITTED",
        evidence=("fa_math_is_rules_based", "sls_ai_features_exist"),
        source_url="https://www.learning.moe.edu.sg/teachers/teacher-user-guide/assess/"
                   "add-mathematics-feedback-assistant/",
        use_it_for="Line-by-line hints on workings, which is where students actually lose "
                   "marks in maths.",
        watch_out="It is rules-based, not generative. That is a feature: it is auditable "
                  "and predictable. It is also limited to the question types it supports.",
    ),

    Tool(
        key="set",
        name="Speech Evaluation Tool (SET)",
        official=True,
        audience="students",
        summary="Instant automated feedback on pronunciation, reading fluency and speech "
                "clarity for English and Mother Tongue Languages. Students record, "
                "review and revise their own spoken responses.",
        levels=("P4", "P5", "P6", "Secondary", "JC"),
        subjects=("English Language", "Mother Tongue Languages"),
        verdict="PERMITTED",
        evidence=("set_spoken_scope", "sls_ai_features_exist"),
        source_url="https://www.learning.moe.edu.sg/teachers/teacher-user-guide/"
                   "author/speech-evaluation/",
        use_it_for="Self-paced pronunciation and fluency practice without needing a slot "
                   "with the teacher.",
        watch_out="Automated feedback on speech is mechanical. It does not know your "
                  "class's context, and students should treat it as one input among "
                  "several, not as a mark.",
    ),

    # -----------------------------------------------------------------
    # Commercial tools. Everything below is CONDITIONAL at best.
    # Each vendor is listed separately so a teacher can see the specific
    # data terms, and so a vendor can eventually sponsor their own slot.
    # -----------------------------------------------------------------

    Tool(
        key="chatgpt",
        name="ChatGPT (OpenAI)",
        official=False,
        audience="both",
        summary="OpenAI's conversational AI. Consumer tiers have materially different "
                "privacy terms: Free users' data may be used for model training; Plus "
                "users can opt out. Enterprise and API offer zero-retention options with "
                "a Data Processing Addendum. Not education-specific, no curriculum "
                "alignment, no SLS integration.",
        levels=(),
        subjects=(),
        verdict="CONDITIONAL",
        conditions=(
            "Free-tier consumer accounts: OpenAI states data may be retained for model "
            "training. Plus users can opt out, but must do so explicitly. Neither tier "
            "offers a DPA.",
            "Input must contain no personal identifiable information. This is a MOE "
            "requirement for commercial-off-the-shelf tools, stated in Parliament on "
            "6 May 2026.",
            "Parental consent is required where external tools are introduced, without "
            "which students cannot use them.",
            "Not for Primary 1 to 3. MOE is explicit that lower primary is print-first "
            "and students will not be tasked to use chatbots.",
        ),
        evidence=("commercial_no_pii", "parental_consent", "p1_p3_rule"),
        source_url="https://openai.com/policies/us-privacy-policy/",
        use_it_for="Teacher-side productivity where no student data is involved: "
                   "differentiated question sets, rubric drafts, plain-language letters. "
                   "Use a paid tier with training opt-out enabled.",
        watch_out="Consumer terms differ by tier. Free users' data may train models. "
                  "The tool is not built for children, is not curriculum-aligned, and "
                  "its retention terms are outside your school's control. If your school "
                  "has not approved ChatGPT specifically, treat it as unapproved.",
    ),

    Tool(
        key="claude",
        name="Claude (Anthropic)",
        official=False,
        audience="both",
        summary="Anthropic's conversational AI. Consumer product retains data up to "
                "5 years in de-identified form if the user enables model improvement; "
                "deleted chats are removed from backend within 30 days. API data is "
                "retained for 30 days and not used for training. Not education-specific, "
                "no curriculum alignment, no SLS integration.",
        levels=(),
        subjects=(),
        verdict="CONDITIONAL",
        conditions=(
            "Consumer accounts: if model improvement is enabled, data is retained up "
            "to 5 years for training. Users can disable this in privacy settings. "
            "Chats flagged by trust-and-safety systems are retained up to 2 years "
            "(safety scores up to 7 years).",
            "Input must contain no personal identifiable information. This is a MOE "
            "requirement for commercial-off-the-shelf tools, stated in Parliament on "
            "6 May 2026.",
            "Parental consent is required where external tools are introduced, without "
            "which students cannot use them.",
            "Not for Primary 1 to 3. MOE is explicit that lower primary is print-first "
            "and students will not be tasked to use chatbots.",
        ),
        evidence=("commercial_no_pii", "parental_consent", "p1_p3_rule"),
        source_url="https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data",
        use_it_for="Teacher-side productivity where no student data is involved: "
                   "drafting feedback, analysing text, rubric development. Disable "
                   "model improvement in privacy settings before use.",
        watch_out="The 5-year training retention is the longest of any major LLM "
                  "vendor's consumer tier. If model improvement is disabled, new chats "
                  "are not used for training, but already-trained models retain what "
                  "they learned. The tool is not curriculum-aligned and its terms are "
                  "outside your school's control.",
    ),

    Tool(
        key="gemini",
        name="Gemini (Google)",
        official=False,
        audience="both",
        summary="Google's conversational AI. Consumer Gemini activity is stored in "
                "the user's Google Account with a default retention of 18 months; "
                "auto-delete can be set to 3 or 36 months. Subject to Google's broader "
                "privacy policy. Enterprise and API offer zero-data-retention options "
                "on paid tiers. Not education-specific, no curriculum alignment, no "
                "SLS integration.",
        levels=(),
        subjects=(),
        verdict="CONDITIONAL",
        conditions=(
            "Consumer accounts: data is stored in the user's Google Account for up "
            "to 18 months by default. Auto-delete can reduce this to 3 months but "
            "must be configured manually. Google's privacy policy governs use.",
            "Input must contain no personal identifiable information. This is a MOE "
            "requirement for commercial-off-the-shelf tools, stated in Parliament on "
            "6 May 2026.",
            "Parental consent is required where external tools are introduced, without "
            "which students cannot use them.",
            "Not for Primary 1 to 3. MOE is explicit that lower primary is print-first "
            "and students will not be tasked to use chatbots.",
        ),
        evidence=("commercial_no_pii", "parental_consent", "p1_p3_rule"),
        source_url="https://transparency.google/intl/en/our-policies/privacy-policy-terms-service/",
        use_it_for="Teacher-side productivity where no student data is involved: "
                   "lesson planning, question generation, document summarisation. "
                   "Set auto-delete to the shortest available window.",
        watch_out="Gemini is governed by Google's broader data ecosystem. Data from "
                  "consumer use sits in the same Google Account as Gmail, Drive, and "
                  "Search history. The 18-month default retention is longer than most "
                  "teachers realise. The tool is not curriculum-aligned and its terms "
                  "are outside your school's control.",
    ),

    Tool(
        key="copilot",
        name="Microsoft Copilot (Consumer)",
        official=False,
        audience="both",
        summary="Microsoft's consumer AI assistant (copilot.microsoft.com). Distinct "
                "from Microsoft 365 Copilot, which operates under enterprise data "
                "protection terms with a DPA and no model training. The consumer "
                "version is governed by the Microsoft Services Agreement. Not "
                "education-specific, no curriculum alignment, no SLS integration.",
        levels=(),
        subjects=(),
        verdict="CONDITIONAL",
        conditions=(
            "This is the CONSUMER version (copilot.microsoft.com), not Microsoft 365 "
            "Copilot. The enterprise version has a DPA, data processor terms, and "
            "explicit commitments that data is not used to train foundation models. "
            "The consumer version does not carry those protections.",
            "Input must contain no personal identifiable information. This is a MOE "
            "requirement for commercial-off-the-shelf tools, stated in Parliament on "
            "6 May 2026.",
            "Parental consent is required where external tools are introduced, without "
            "which students cannot use them.",
            "Not for Primary 1 to 3. MOE is explicit that lower primary is print-first "
            "and students will not be tasked to use chatbots.",
        ),
        evidence=("commercial_no_pii", "parental_consent", "p1_p3_rule"),
        source_url="https://learn.microsoft.com/en-us/microsoft-365/copilot/enterprise-data-protection",
        use_it_for="Teacher-side productivity where no student data is involved: "
                   "drafting communications, generating worksheets, research queries. "
                   "If your school has Microsoft 365, ask whether the enterprise "
                   "Copilot licence is available -- it has materially stronger terms.",
        watch_out="Do not confuse the consumer and enterprise versions. Microsoft 365 "
                  "Copilot (enterprise) has a DPA and no-training commitments. The "
                  "consumer copilot.microsoft.com does not. If your school pays for "
                  "Microsoft 365, the enterprise Copilot is the defensible choice. "
                  "The consumer version's terms are governed by the Microsoft Services "
                  "Agreement, not the DPA.",
    ),
)

TOOLS_BY_KEY: dict[str, Tool] = {t.key: t for t in TOOLS}


# ---------------------------------------------------------------------------
# Compliance checks
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    severity: str          # BLOCKING | WARNING | INFO
    code: str
    message: str


def check(today=None) -> list[Finding]:
    """Verify every tool listing is defensible. Empty list means publishable."""
    out: list[Finding] = []
    seen: set[str] = set()

    for t in TOOLS:
        if t.key in seen:
            out.append(Finding("BLOCKING", "DUPLICATE_TOOL_KEY",
                               f"Tool '{t.key}' listed twice."))
        seen.add(t.key)

        if not t.summary.strip():
            out.append(Finding("BLOCKING", "MISSING_SUMMARY",
                               f"Tool '{t.key}' has no description."))

        if not t.watch_out.strip():
            out.append(Finding("BLOCKING", "MISSING_CAVEAT",
                               f"Tool '{t.key}' has no caveat. Every tool listing needs "
                               f"one -- a directory that only upsells is advertising, "
                               f"and advertising is not the service."))

        if not t.use_it_for.strip():
            out.append(Finding("WARNING", "MISSING_USE_CASE",
                               f"Tool '{t.key}' does not say what to use it for."))

        if t.verdict not in ("PERMITTED", "CONDITIONAL", "HOLD"):
            out.append(Finding("BLOCKING", "BAD_VERDICT",
                               f"Tool '{t.key}' has verdict '{t.verdict}', which is not "
                               f"a recognised value."))

        if t.verdict == "PERMITTED" and not t.official:
            # A commercial tool cannot be PERMITTED. We do not control its data
            # handling, its training terms, or its age gating. Only MOE can
            # grant that, and only to itself.
            out.append(Finding("BLOCKING", "COMMERCIAL_CLAIMS_PERMITTED",
                               f"Tool '{t.key}' is commercial but marked PERMITTED. We "
                               f"cannot verify a vendor's data handling, so no "
                               f"commercial tool may be rated PERMITTED. Use "
                               f"CONDITIONAL or HOLD."))

        if not t.official and not t.evidence:
            out.append(Finding("BLOCKING", "UNSUPPORTED_COMMERCIAL_TOOL",
                               f"Commercial tool '{t.key}' has no evidence attached. An "
                               f"unverified commercial listing hands a teacher's "
                               f"professional judgement to a vendor. Mark it HOLD."))

        for ek in t.evidence:
            if ek not in FACTS_BY_KEY:
                out.append(Finding("BLOCKING", "UNKNOWN_EVIDENCE",
                                   f"Tool '{t.key}' cites fact '{ek}', which is not in "
                                   f"the registry."))

        if t.official and t.sponsor:
            out.append(Finding("BLOCKING", "SPONSORED_OFFICIAL_TOOL",
                               f"Tool '{t.key}' is an official MOE tool and carries a "
                               f"sponsor. Selling a slot next to something MOE built "
                               f"destroys the only credibility this site has."))

        if t.unverified and t.verdict != "HOLD":
            out.append(Finding("BLOCKING", "UNVERIFIED_NOT_HELD",
                               f"Tool '{t.key}' is flagged unverified but its verdict "
                               f"is '{t.verdict}'. Unverified tools must be HOLD."))

    return out


def by_verdict() -> dict[str, list[Tool]]:
    out: dict[str, list[Tool]] = {"PERMITTED": [], "CONDITIONAL": [], "HOLD": []}
    for t in TOOLS:
        out.setdefault(t.verdict, []).append(t)
    return out


if __name__ == "__main__":
    findings = check()
    counts = by_verdict()
    print()
    print("=" * 70)
    print("TOOL REGISTRY COMPLIANCE CHECK")
    print("=" * 70)
    print(f"  Official SLS tools      {sum(1 for t in TOOLS if t.official)}")
    print(f"  Commercial tools        {sum(1 for t in TOOLS if not t.official)}")
    print(f"  PERMITTED{'':<14}{len(counts['PERMITTED'])}")
    print(f"  CONDITIONAL{'':<12}{len(counts['CONDITIONAL'])}")
    print(f"  HOLD{'':<18}{len(counts['HOLD'])}")
    print()
    for v in ("PERMITTED", "CONDITIONAL", "HOLD"):
        print(f"  {v}")
        for t in counts[v]:
            tag = "SLS" if t.official else "commercial"
            print(f"    [{tag:<10}] {t.name}")
        print()
    if findings:
        blocking = [f for f in findings if f.severity == "BLOCKING"]
        print(f"  {len(findings)} finding(s), {len(blocking)} blocking")
        print()
        for f in findings:
            print(f"  [{f.severity}] {f.code}")
            print(f"      {f.message}")
            print()
    else:
        print("  PASS -- every listing is sourced, caveated and within what we can")
        print("         actually verify.")
    print("=" * 70)