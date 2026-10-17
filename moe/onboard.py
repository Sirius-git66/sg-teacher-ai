"""First-timer Q&A — the onboarding a teacher sees before they use the checker.

This is not a chatbot. It is a fixed set of questions with pre-vetted answers,
each traced to the fact registry or explicitly marked as our own framing.

Two rules:
  1. Every answer that cites MOE must cite a real fact key. An answer citing
     a nonexistent key renders with no source — the one failure a compliance
     site cannot ship.
  2. At least some answers are OUR framing, not MOE claims. If every answer
     carried a citation, we would be borrowing MOE's authority for our own
     opinions. The uncited answers say so explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Question:
    """One onboarding question with a pre-vetted answer.

    `evidence` is a tuple of fact keys. Empty means the answer is our own
    framing, not a MOE claim — and it must say so.
    """

    q: str
    a: tuple[str, ...]
    evidence: tuple[str, ...] = ()


QUESTIONS: tuple[Question, ...] = (
    Question(
        q="What is this site?",
        a=(
            "This is a reference site for Singapore teachers answering one "
            "question: what can I actually use, at my level, under MOE rules?",
            "Every claim on this site traces back to a verbatim quote from MOE "
            "with a clickable source link. We are not affiliated with MOE. We are "
            "not a government site. We are a fact-checking tool that happens to "
            "look like a website.",
        ),
    ),
    Question(
        q="Who built this? Is it official?",
        a=(
            "This site is not affiliated with, endorsed by, or connected to the "
            "Ministry of Education, Singapore. It is an independent reference "
            "built by someone who reads MOE's published sources and checks them "
            "on a schedule.",
            "MOE publishes the rules. We organise them so a teacher can find "
            "the answer in ten seconds instead of forty minutes of page-scrolling.",
        ),
    ),
    Question(
        q="How do I know the answers are correct?",
        a=(
            "Every answer links to its MOE source. Click the link. Read the "
            "quote. Check the date we last verified it. If we are wrong, the "
            "source will show you.",
            "That is the safeguard a 'trust us, we're experts' site cannot "
            "offer. We do not ask you to trust us. We ask you to check us.",
        ),
        evidence=("moe_commitments",),
    ),
    Question(
        q="Can I use ChatGPT with my students?",
        a=(
            "The short answer: only with your school's explicit approval, "
            "parental consent, and no student personal data in the input.",
            "A general-purpose chatbot is not 'specifically designed for "
            "education', which is what MOE requires for Primary 4 to 6. At "
            "Secondary and JC, students take greater ownership of AI use — "
            "but ownership is responsibility, not permission. The school still "
            "needs to approve the tool.",
        ),
        evidence=("commercial_no_pii", "parental_consent", "p4_p6_rule"),
    ),
    Question(
        q="What about at Primary 1 to 3?",
        a=(
            "No. MOE is explicit: Primary 1 to 3 is hands-on and print-first. "
            "Students learn what AI is and where it appears in daily life, but "
            "schools will not assign any work that requires them to use AI "
            "directly. Students will not be tasked to use chatbots.",
            "This applies to every AI tool — official or commercial. There is "
            "no exception at this level.",
        ),
        evidence=("p1_p3_rule",),
    ),
    Question(
        q="Do I need parental consent?",
        a=(
            "Yes. Where external AI tools are introduced, parental consent is "
            "required. If consent is not obtained, students will not be allowed "
            "to use those tools.",
            "This applies to commercial tools and any tool not built by MOE "
            "into the Student Learning Space. Official SLS tools are covered "
            "by MOE's own data governance and do not require separate consent.",
        ),
        evidence=("parental_consent", "moe_data_anonymised"),
    ),
    Question(
        q="Can my school approve a tool that you rate as CONDITIONAL?",
        a=(
            "Your school can approve the use of a tool, but it cannot change "
            "what we can verify. We rate a tool CONDITIONAL when we cannot "
            "audit the vendor's data handling, training terms, or age gating. "
            "Your school's approval is an institutional decision; our verdict "
            "is a statement of what the evidence shows.",
            "If a vendor provides verifiable data-retention terms, we will "
            "re-evaluate. But we cannot audit a vendor we have not reviewed.",
        ),
    ),
    Question(
        q="What will this site NOT tell me?",
        a=(
            "We will not tell you a tool is safe when we have not checked it. "
            "We will not rate a commercial tool as 'permitted' — we cannot "
            "audit a vendor's data handling, so the ceiling is 'usable under "
            "conditions'. We will not give you a chatbot answer in prose we "
            "cannot cite.",
            "We will not promote private services to students or parents "
            "through this site. We will not pretend that a well-formatted list "
            "is the same as a verified claim.",
            "If the question falls outside what we have pre-vetted, we will "
            "say so and tell you who to ask instead.",
        ),
    ),
    Question(
        q="What should I do if I'm not sure?",
        a=(
            "The safe default: do not use the tool with students until your "
            "school has approved it. Ask your school's AI coordinator. Check "
            "MOE's official guidance.",
            "If you are a teacher and you are not yet comfortable with AI "
            "tools, that is fine. MOE is rolling out a Teacher AI Literacy "
            "Professional Learning Roadmap. The first compulsory module is "
            "due end of 2026. You are not behind — the landscape is still "
            "being built.",
        ),
    ),
    Question(
        q="What does 'students take greater ownership' actually mean?",
        a=(
            "It means students at Secondary and pre-university learn to "
            "evaluate AI output, check its accuracy, acknowledge AI use where "
            "required, and uphold academic integrity.",
            "It does NOT mean students are freely permitted to use any AI "
            "tool. Ownership is responsibility — the student carries the "
            "obligation to use AI honestly. It is not clearance to use a "
            "general-purpose chatbot without school approval. This is the "
            "single most common misreading of MOE's guidance.",
        ),
        evidence=("secondary_rule", "disclosure_rule"),
    ),
)


def by_index(n: int) -> Optional[Question]:
    """Look up a question by 1-based index. Returns None for out-of-range.

    Questions are numbered 1 to len(QUESTIONS). Index 0 and index
    len(QUESTIONS)+1 both return None — the caller gets no wrong answer,
    only an honest absence.
    """
    if 1 <= n <= len(QUESTIONS):
        return QUESTIONS[n - 1]
    return None
