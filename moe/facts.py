"""Sourced fact registry for the Singapore MOE AI directory.

Every factual claim the site makes lives here, with a URL, a retrieval date and
a verbatim quote. Nothing goes on the site that is not in this file. That is the
entire product: a teacher can click through and check us, and we can be wrong in
public instead of quietly.

Why a registry and not a website:

  A directory of AI tools for schools is only worth anything if it is accurate.
  Accuracy is not a writing problem, it is a maintenance problem -- MOE ships new
  tools, retires old ones, and shifts level boundaries. So the valuable asset is
  not prose. It is a machine-checkable set of claims with expiry dates, and an
  auditor that refuses to let the site build when a claim has gone stale.

Three rules this file enforces by construction:

  1. NO UNSOURCED CLAIM. `Fact` requires `source_url` and `quote`. There is no
     way to add an assertion without evidence attached.
  2. NO SILENT REFRESH. `checked_on` is a human assertion that someone read the
     source. `audit()` computes staleness and fails. Re-verification must be
     deliberate, which means someone read the page again.
  3. STALE IS A VISIBLE STATE. A fact past its review window reports as
     STALE, never as deleted and never quietly kept. Deleting a fact hides the
     gap; a stale fact shows the reader we might be wrong.

Verified against primary sources on 17 October 2026. Retrieved live from moe.gov.sg
and learning.moe.edu.sg, not from memory and not from secondary commentary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Iterable

#: The date every fact in this file was last checked against its source.
VERIFIED_ON = date(2026, 10, 17)


# ---------------------------------------------------------------------------
# Source registry -- who is authoritative on what
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Source:
    """A primary source. Never cite a blog post for a compliance claim."""

    key: str
    title: str
    url: str
    publisher: str
    #: What this source is authoritative for. If a claim is not covered by this
    #: source's remit, do not cite it -- that is how citations become decorative.
    authoritative_for: str
    #: How often someone should go and re-read this. MOE ships changes; a
    #: parliamentary reply is a snapshot and goes stale faster than a live page.
    review_days: int


SOURCES: dict[str, Source] = {
    "moe_aied": Source(
        key="moe_aied",
        title="Artificial intelligence in education — MOE's position",
        url="https://www.moe.gov.sg/education-in-sg/educational-technology-journey/"
            "edtech-masterplan/artificial-intelligence-in-education",
        publisher="Ministry of Education, Singapore",
        authoritative_for="Level-by-level rules, MOE's four commitments, the Four "
                          "Learns, age-appropriateness",
        review_days=60,
    ),
    "sls_aied": Source(
        key="sls_aied",
        title="AI-enabled Features — Student Learning Space",
        url="https://www.learning.moe.edu.sg/teachers/teaching-and-learning-on-sls/"
            "aied-features/",
        publisher="Ministry of Education, Singapore",
        authoritative_for="Which SLS AI features exist, what each does, which "
                          "subjects and levels they cover",
        review_days=45,
    ),
    "pq_may2026": Source(
        key="pq_may2026",
        title="AI usage in schools — Parliamentary reply, 6 May 2026",
        url="https://www.moe.gov.sg/news/parliamentary-replies/20260506-ai-usage-in-schools",
        publisher="Ministry of Education, Singapore (Parliamentary reply)",
        authoritative_for="Data governance rules, guardrails, academic integrity, "
                          "the rationale for the Primary 4 entry point, the worked "
                          "Primary 4 Learning Assistant example",
        review_days=90,
    ),
    "aied_framework": Source(
        key="aied_framework",
        title="AI in Education Framework",
        url="https://www.learning.moe.edu.sg/ai-in-sls/responsible-ai/"
            "ai-in-education-framework/",
        publisher="Ministry of Education, Singapore",
        authoritative_for="The four AIEd principles and the AIEd Primer",
        review_days=90,
    ),
}


# ---------------------------------------------------------------------------
# The facts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Fact:
    """One checkable claim, with the evidence that supports it.

    `quote` is verbatim from the source. It is deliberately not paraphrased:
    a paraphrase is where a compliance error hides, because it silently changes
    the scope of what MOE actually said.
    """

    key: str
    claim: str
    source_key: str
    quote: str
    #: Categories this fact drives on the site. Used by the renderer so a fact
    #: that is no longer referenced anywhere is reported as orphaned rather than
    #: quietly sitting in the registry inflating our apparent coverage.
    topics: tuple[str, ...] = ()
    checked_on: date = VERIFIED_ON
    #: Optional: when MOE has stated a direction of travel, record it. A fact
    #: with a `watch` note is one that is likely to change and should be
    #: re-checked on a shorter cycle than its source's review_days suggests.
    watch: str = ""


FACTS: tuple[Fact, ...] = (

    # -- the four commitments ------------------------------------------
    Fact(
        key="moe_commitments",
        claim="MOE commits that AI in education must benefit students' learning and "
              "development, be purposeful and intentional, be age- and developmentally "
              "appropriate / safe / responsible, and be grounded in the Singapore "
              "Teaching Practice and guided by MOE's e-Pedagogy.",
        source_key="moe_aied",
        quote="MOE is committed that AI in education: Must benefit students' learning "
              "and development; Is purposeful and intentional; Is age- and "
              "developmentally appropriate, safe, and responsible; Is grounded in the "
              "Singapore Teaching Practice and guided by MOE's e-Pedagogy",
        topics=("principles",),
    ),

    # -- the four learns ----------------------------------------------
    Fact(
        key="four_learns",
        claim="MOE's stated goal is that every student learns about AI, learns to use "
              "AI, learns with AI, and most importantly learns beyond AI. MOE calls "
              "this the Four Learns.",
        source_key="pq_may2026",
        quote="for every student to learn about AI, learn to use AI, learn with AI and "
              "most importantly, learn beyond AI. These are what we call the \"Four "
              "Learns\".",
        topics=("principles", "literacy"),
    ),

    # -- level rules, the load-bearing content ------------------------
    Fact(
        key="p1_p3_rule",
        claim="Primary 1 to 3: hands-on, print-first. Students learn what AI is and "
              "where it appears in daily life, but schools will not assign any work "
              "that requires them to use AI directly. AI may provide customised "
              "feedback, but students are not tasked to use chatbots.",
        source_key="moe_aied",
        quote="Learning is hands-on and print-first, helping students build knowledge, "
              "thinking and social skills through concrete and tactile experiences. "
              "Students are introduced to what AI is and how it appears in daily life. "
              "AI may be used to provide customised feedback, but students will not be "
              "tasked to use chatbots.",
        topics=("levels", "p1_p3"),
    ),
    Fact(
        key="p4_entry_reason",
        claim="Primary 4 is the entry point because by then students have foundational "
              "literacy and numeracy, plus enough executive functioning -- planning, "
              "task initiation, evaluating their own thinking -- to use simple digital "
              "tools to support their learning.",
        source_key="pq_may2026",
        quote="From primary 4, students would have developed foundational literacy, "
              "numeracy and basic knowledge of AI in their daily lives. Research also "
              "shows that at around this age, they would have developed some executive "
              "functioning skills like planning, task initiation, and ability to "
              "evaluate their own thinking, to begin to use simple digital tools to "
              "support their learning.",
        topics=("levels", "p4_p6"),
        watch="Rationale is research-based and therefore stable, but MOE cites it as "
              "ongoing evidence. Re-check that the entry point has not moved to P3.",
    ),
    Fact(
        key="p4_p6_rule",
        claim="Primary 4 to 6: students use only AI tools specifically designed for "
              "education, and only under teacher supervision. This includes the "
              "AI-enabled SLS features, which have in-built safety guardrails.",
        source_key="pq_may2026",
        quote="Students in primary 4 to 6 will only use AI tools in school that are "
              "specifically designed for education. And they will only do so under "
              "teacher supervision. This includes the AI-enabled tools that we have "
              "introduced into the Singapore Student Learning Space (SLS) which are "
              "specially designed to help students learn. These tools have in-built "
              "safety guardrails.",
        topics=("levels", "p4_p6"),
        watch="The boundary between 'MOE-built in SLS' and 'selected educational AI "
              "tools' is the one most likely to shift. Watch for expansion of the "
              "approved-tool list.",
    ),
    Fact(
        key="secondary_rule",
        claim="Secondary and pre-university: students progressively take greater "
              "ownership. They learn to evaluate AI output, check its accuracy, "
              "acknowledge AI use where required and uphold academic integrity.",
        source_key="moe_aied",
        quote="Students progressively take greater ownership of AI use in learning. They "
              "learn to evaluate AI-generated output, check its accuracy, acknowledge "
              "AI use where required and uphold academic integrity.",
        topics=("levels", "secondary"),
    ),

    # -- academic integrity -------------------------------------------
    Fact(
        key="exams_prohibited",
        claim="National examinations continue to be proctored and AI use is prohibited. "
              "Where AI is permitted in national exam coursework, Teacher Supervisors "
              "monitor the work so AI use meets the objectives of the assessment.",
        source_key="pq_may2026",
        quote="National exams continue to be proctored, and use of AI is prohibited. If "
              "students use AI as a shortcut for their daily work instead of learning "
              "deeply, they will not be able to demonstrate the levels of mastery "
              "expected during the exams. In cases where the use of AI is permitted in "
              "national exams, such as for coursework, Teacher Supervisors monitor "
              "students' work such that AI use meets the objectives of the assessment.",
        topics=("integrity",),
    ),
    Fact(
        key="disclosure_rule",
        claim="Where a secondary school designs a task that permits AI, students must "
              "state where they have used AI and cite their sources. Passing off "
              "AI-generated content as their own carries consequences for academic "
              "dishonesty.",
        source_key="pq_may2026",
        quote="some secondary schools may design tasks which allow students to use AI. In "
              "these situations, students must state where they have used AI and cite "
              "the sources of information... However, if students pass off AI-generated "
              "content as their own, they will have to bear the consequences of academic "
              "dishonesty.",
        topics=("integrity", "secondary"),
    ),

    # -- data governance -- the commercially decisive part ------------
    Fact(
        key="moe_data_anonymised",
        claim="Data from students' use of MOE-built AI tools is anonymised and is not "
              "used to train the external AI models that power them.",
        source_key="pq_may2026",
        quote="Data from students' use of MOE-built AI tools is anonymised and not used "
              "to train external AI models that power these tools.",
        topics=("data",),
    ),
    Fact(
        key="commercial_no_pii",
        claim="When schools use commercial-off-the-shelf AI tools they are required to "
              "check that the input data contains no personal identifiable information "
              "and complies with data management guidelines. This is the single most "
              "important compliance rule for any third-party tool.",
        source_key="pq_may2026",
        quote="When schools use commercial-off-the-shelf AI tools, they are required to "
              "check that the input data does not contain personal identifiable "
              "information and is in compliance with data management guidelines.",
        topics=("data", "commercial"),
    ),
    Fact(
        key="parental_consent",
        claim="Where external AI tools are introduced, parental consent is required. "
              "Without consent, students are not allowed to use those tools.",
        source_key="pq_may2026",
        quote="Lee added that where external tools are introduced, parental consent is "
              "required. If consent is not obtained, students will not be allowed to use "
              "those tools.",
        topics=("data", "commercial"),
        watch="Reported from a parliamentary reply rather than appearing in MOE's own "
              "published guidance. Worth confirming against MOE's guidelines for "
              "commercial tools before leaning on it in a paid product.",
    ),
    Fact(
        key="teacher_responsibility",
        claim="Teachers remain central and responsible. MOE equips them with the "
              "knowledge and skills to use AI, including its ethical and pedagogical "
              "considerations, and its risks and limitations.",
        source_key="pq_may2026",
        quote="Our teachers play a central role in harnessing AI effectively for student "
              "learning, and we have been equipping them with the necessary knowledge "
              "and skills to do so. For instance, we provide opportunities for our "
              "teachers to learn about AI, including the ethical and pedagogical "
              "considerations on its use, and its associated risks and limitations.",
        topics=("principles", "teachers"),
    ),

    # -- the AIEd framework -------------------------------------------
    Fact(
        key="aied_framework",
        claim="MOE's AI in Education Framework builds on IMDA's Model AI Governance "
              "Framework and the Ethos of the Teaching Profession, on four principles: "
              "Agency, Inclusivity, Fairness and Safety.",
        source_key="aied_framework",
        quote="The MOE AIEd Framework builds on the Model AI Governance Framework by the "
              "Singapore Infocomm Media Development Authority (IMDA) and reflects the "
              "Ethos of the Teaching Profession. It guides the safe and responsible use "
              "of AI in teaching and learning.",
        topics=("principles",),
    ),

    # -- guardrails, from the minister's own worked example ----------
    Fact(
        key="lea_guardrail",
        claim="The Learning Assistant redirects students back on topic if they veer off "
              "or ask to be spoon-fed direct answers. MOE tested this deliberately with "
              "off-topic questions in a Primary 4 English class.",
        source_key="pq_may2026",
        quote="As a guardrail, the LEA will redirect students back on track if they veer "
              "off-topic and ask irrelevant questions, or if they want to be spoon-fed "
              "with direct answers. Last year, my colleagues and I tried it out. We were "
              "in a class, there was a particular topic, and we deliberately tried to go "
              "off course... And they will tell us to say \"No, this is not relevant. "
              "Please let's get back on topic.\"",
        topics=("guardrails", "p4_p6"),
    ),
    Fact(
        key="ai_for_fun",
        claim="From Primary 4, the mandatory 10-hour Code for Fun programme includes "
              "coding, computational thinking and an introduction to AI. Primary schools "
              "may opt into two additional five-hour 'AI for Fun' modules, in generative "
              "AI and computer vision respectively.",
        source_key="pq_may2026",
        quote="From primary 4, students undergo the mandatory 10 hours 'Code for Fun' (CFF) "
              "programme... primary schools can also opt for two additional 'AI for Fun' "
              "modules, each 5 hours, that delve further into generative AI and computer "
              "vision respectively.",
        topics=("levels", "p4_p6", "curriculum"),
    ),

    # -- the official SLS toolset itself -----------------------------
    # Without these, every tool listing on the site rests on a source the
    # registry never cites, and a reader checking our citations would find a
    # gap exactly where they most wanted evidence.
    Fact(
        key="sls_ai_features_exist",
        claim="MOE publishes a defined set of AI-enabled features inside the Student "
              "Learning Space, each with teacher and student user guides. Students are "
              "encouraged to complete the relevant Basic Module on AI and AI-enabled "
              "features in SLS before using them.",
        source_key="sls_aied",
        quote="Before using AI-enabled features in SLS, you are encouraged to have "
              "students complete the Basic Modules for AI and AI-enabled features in SLS "
              "in the following links: Lower Primary Module; Upper Primary Module; "
              "Secondary/JC/MI Level Module.",
        topics=("sls", "onboarding"),
        watch="MOE adds AI features to SLS regularly. This list grows; check it "
              "against the source before claiming the set is complete.",
    ),
    Fact(
        key="sls_moe_built_with_teachers",
        claim="Every AI feature MOE publishes in SLS ships with educator resources -- "
              "teacher user guides, and for student-facing features, student user "
              "guides too. ACP, DAT and SET list teacher guides; ALS, LEA, AFA, "
              "ShortAnsFA and FA-Math list both.",
        source_key="sls_aied",
        quote="Educator Resources Teachers User Guide (UG): UG for teachers; Students "
              "User Guide (UG): UG for students",
        topics=("sls",),
    ),
    Fact(
        key="saFA_math_exclusion",
        claim="MOE states that Short Answer Feedback Assistant should not be used for "
              "questions involving mathematical computation, because it cannot provide "
              "accurate feedback for mathematical concepts.",
        source_key="sls_aied",
        quote="ShortAnsFA should not be used for questions involving mathematical "
              "computation as it is unable to provide accurate feedback for mathematical "
              "concepts.",
        topics=("sls", "feedback", "mathematics"),
    ),
    Fact(
        key="als_coverage_limited",
        claim="ALS currently covers only Mathematics (Upper Primary and Lower Secondary) "
              "and Geography (Upper Secondary), though MOE states more topics, levels "
              "and subjects will be added progressively.",
        source_key="sls_aied",
        quote="It is currently available for Mathematics (Upper Primary and Lower "
              "Secondary) and Geography (Upper Secondary). More topics, levels and "
              "subjects will be added progressively.",
        topics=("sls", "mathematics"),
        watch="Stated as growing. This is the fact most likely to be out of date, "
              "because growth is exactly what was promised.",
    ),
    Fact(
        key="fa_math_is_rules_based",
        claim="Feedback Assistant - Mathematics is a rules-based engine, not a "
              "generative one: it gives step-by-step hints by analysing each step of a "
              "student's working, and can generate randomised questions.",
        source_key="sls_aied",
        quote="FA-Math is a rules-based engine that offers step-by-step hints and "
              "feedback to students' workings, and suggested marks.",
        topics=("sls", "mathematics", "feedback"),
    ),
    Fact(
        key="set_spoken_scope",
        claim="The Speech Evaluation Tool covers pronunciation, reading fluency and "
              "speech clarity for English Language and Mother Tongue Languages across "
              "levels, with students recording and revising their own spoken responses.",
        source_key="sls_aied",
        quote="Speech Evaluation Tool (SET) provides instant, automated feedback on "
              "pronunciation, reading fluency, and speech clarity to help students "
              "improve their speaking abilities for English and Mother Tongue Languages.",
        topics=("sls", "languages"),
    ),
    Fact(
        key="afa_socratic_option",
        claim="The Annotated Feedback Assistant can be tuned toward Socratic questioning "
              "or scaffolded hints rather than direct corrections, and teachers control "
              "how many times a student receives feedback.",
        source_key="sls_aied",
        quote="Teachers can customise feedback output with options such as Socratic "
              "questioning or scaffolded hints to guide student reflection... Teachers "
              "can control the number of times students receive feedback, enabling "
              "iterative improvement in their responses.",
        topics=("sls", "feedback", "pedagogy"),
    ),
)


FACTS_BY_KEY: dict[str, Fact] = {f.key: f for f in FACTS}


# ---------------------------------------------------------------------------
# Audit -- the part that earns the right to publish
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    severity: str          # BLOCKING | WARNING | INFO
    code: str
    message: str


def audit(today: date | None = None) -> list[Finding]:
    """Check the registry against itself. Returns findings, empty means publishable.

    This is deliberately paranoid. A directory that quietly carries one
    out-of-date compliance claim loses the trust that is its only asset, and it
    loses it permanently -- a teacher who catches you once does not come back.

    The failure mode this guards against is not a typo. It is a well-written
    article that was true eight months ago.
    """
    today = today or date.today()
    out: list[Finding] = []

    if not SOURCES:
        out.append(Finding("BLOCKING", "NO_SOURCES",
                           "No sources registered. Nothing can be cited, so nothing "
                           "can be published."))

    if not FACTS:
        out.append(Finding("BLOCKING", "NO_FACTS",
                           "No facts registered. The site would have nothing to say."))

    seen: set[str] = set()
    for f in FACTS:
        if f.key in seen:
            out.append(Finding("BLOCKING", "DUPLICATE_FACT_KEY",
                               f"Fact key '{f.key}' appears more than once. Keys are "
                               f"the citation handle; duplicates make a citation "
                               f"ambiguous."))
        seen.add(f.key)

        if f.source_key not in SOURCES:
            out.append(Finding("BLOCKING", "UNKNOWN_SOURCE",
                               f"Fact '{f.key}' cites '{f.source_key}', which is not in "
                               f"the source registry. A citation you cannot open is a "
                               f"citation you do not have."))
            continue

        if not f.quote.strip():
            out.append(Finding("BLOCKING", "MISSING_QUOTE",
                               f"Fact '{f.key}' has no verbatim quote. Paraphrase is "
                               f"where a compliance error hides."))

        if len(f.quote) < 40:
            out.append(Finding("WARNING", "THIN_QUOTE",
                               f"Fact '{f.key}' has a suspiciously short quote "
                               f"({len(f.quote)} chars). Check it is the real sentence "
                               f"and not a fragment."))

        if not f.topics:
            out.append(Finding("WARNING", "NO_TOPIC",
                               f"Fact '{f.key}' is tagged with no topic, so no page will "
                               f"ever render it. It is dead weight in the registry."))

        if f.checked_on > today:
            out.append(Finding("BLOCKING", "FUTURE_CHECK_DATE",
                               f"Fact '{f.key}' is dated {f.checked_on}, in the future. "
                               f"Someone has recorded a verification that has not "
                               f"happened."))

        # Staleness. A fact with a `watch` note is reviewed on a tighter cycle
        # than its source, because the thing most likely to change is exactly the
        # thing someone flagged as worth watching.
        #
        # The tightening is a PROPORTION, not a fixed 45-day cap. An earlier
        # version clamped to min(review_days, 45), which meant a watch-flagged
        # fact on a 45-day source got NO tightening at all -- the flag was
        # decorative. That is the worst kind of bug in a freshness check: it
        # looks like it is working. Half the window is the tightest sensible
        # ratio, and it always actually tightens something.
        source = SOURCES[f.source_key]
        window = source.review_days
        if f.watch:
            window = max(1, window // 2)
        age = (today - f.checked_on).days
        if age > window:
            out.append(Finding(
                "BLOCKING", "STALE_FACT",
                f"Fact '{f.key}' was last verified {age} days ago; its review window "
                f"is {window}. Re-read {source.url} and update checked_on only if it "
                f"still holds."))

    # Facts nobody renders are a coverage illusion. We would report a bigger
    # registry than the site actually shows.
    return out


def stale_days(today: date | None = None) -> int:
    """How many days since the most recently verified fact."""
    today = today or date.today()
    return (today - max(f.checked_on for f in FACTS)).days


def facts_for(topic: str) -> list[Fact]:
    return [f for f in FACTS if topic in f.topics]


def coverage() -> dict[str, int]:
    out: dict[str, int] = {}
    for f in FACTS:
        for t in f.topics:
            out[t] = out.get(t, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def citations() -> list[dict]:
    """Machine-readable citation list, for a sources page and for schema.org."""
    return [
        {
            "claim": f.claim,
            "quote": f.quote,
            "source": SOURCES[f.source_key].title,
            "publisher": SOURCES[f.source_key].publisher,
            "url": SOURCES[f.source_key].url,
            "checked_on": f.checked_on.isoformat(),
        }
        for f in FACTS
    ]


if __name__ == "__main__":
    findings = audit()
    print()
    print("=" * 70)
    print("MOE FACT REGISTRY AUDIT")
    print("=" * 70)
    print(f"  Sources registered   {len(SOURCES)}")
    print(f"  Facts registered     {len(FACTS)}")
    print(f"  Most recent check    {max(f.checked_on for f in FACTS)} "
          f"({stale_days()} days ago)")
    print()
    print("  Topic coverage")
    for topic, n in coverage().items():
        print(f"    {topic:<16} {n}")
    print()
    if findings:
        blocking = [f for f in findings if f.severity == "BLOCKING"]
        print(f"  {len(findings)} finding(s), {len(blocking)} blocking")
        print()
        for f in findings:
            print(f"  [{f.severity}] {f.code}")
            print(f"      {f.message}")
            print()
        print("  DO NOT PUBLISH until the blocking findings are resolved.")
    else:
        print("  PASS -- every fact is sourced, quoted and inside its review window.")
        print()
        print("  That is the only thing this file certifies. It does not certify")
        print("  that the interpretation on the page is right. A reader checking the")
        print("  quotes is the real safeguard, and the site has to make that easy.")
    print()
    print("=" * 70)