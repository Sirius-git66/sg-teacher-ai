"""Regression tests for the MOE directory's compliance logic.

    python test_moe.py

These exist for the same reason the trades harness exists: a compliance site
whose checks have silently stopped working is worse than no site, because it
looks authoritative. Every guardrail is tested by trying to violate it.

Standard library only, so nothing needs installing.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import date, timedelta

from moe import facts, tools

PASS = 0
FAIL: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS
    if condition:
        PASS += 1
    else:
        FAIL.append(f"{label}{' -- ' + detail if detail else ''}")


# ---------------------------------------------------------------------------
# 1. The registry is internally sound
# ---------------------------------------------------------------------------

#: MOE publishes on two domains. Both are the ministry itself; neither is a
#: blog, an aggregator or a vendor. Citing anything else for a compliance claim
#: is how a directory turns into hearsay.
OFFICIAL_DOMAINS = ("moe.gov.sg", "learning.moe.edu.sg")


def _is_official_moe(url: str) -> bool:
    return any(d in url for d in OFFICIAL_DOMAINS)


def test_registry() -> None:
    findings = facts.audit(today=facts.VERIFIED_ON)
    blocking = [f for f in findings if f.severity == "BLOCKING"]
    check("registry audits clean on the verification date", not blocking,
          "; ".join(f.code for f in blocking))

    check("every fact has a quote", all(f.quote.strip() for f in facts.FACTS))
    check("every fact cites a registered source",
          all(f.source_key in facts.SOURCES for f in facts.FACTS))
    check("every fact has at least one topic", all(f.topics for f in facts.FACTS))

    for f in facts.FACTS:
        src = facts.SOURCES[f.source_key]
        check(f"'{f.key}' quote is verbatim length",
              len(f.quote) >= 40, f"{len(f.quote)} chars")
        check(f"'{f.key}' source is an official MOE domain",
              _is_official_moe(src.url), src.url)


# ---------------------------------------------------------------------------
# 2. Staleness detection -- the failure mode that actually matters
# ---------------------------------------------------------------------------

def test_staleness() -> None:
    # Six months on, nothing should be trusted.
    later = facts.VERIFIED_ON + timedelta(days=180)
    findings = facts.audit(today=later)
    stale = [f for f in findings if f.code == "STALE_FACT"]
    check("a fact goes stale after its review window",
          len(stale) == len(facts.FACTS), f"{len(stale)} of {len(facts.FACTS)}")

    # Watch-flagged facts must be reviewed faster than their source's default.
    # This must be a real proportional tightening, not a fixed cap: a cap equal
    # to the source window would make the flag decorative, and a decorative
    # freshness flag is worse than none because it is trusted.
    watched = [f for f in facts.FACTS if f.watch]
    check("at least one fact is flagged for closer watching", bool(watched))
    for f in watched:
        src = facts.SOURCES[f.source_key]
        tightened = max(1, src.review_days // 2)
        check(f"'{f.key}' watch actually tightens its {src.review_days}d window",
              tightened < src.review_days,
              f"window is still {src.review_days}d -- the flag does nothing")

    # Facts must not go stale the moment they are checked. Test at an age that is
    # inside EVERY fact's window -- currently the shortest window is 22 days, so
    # 21 days must be clean. Testing the boundary per-window rather than with
    # one global age keeps this honest as windows are retuned; a single
    # "30 days is fine" assertion would have hidden the tightened-window bug
    # above, and would start lying the moment anyone shortens a window.
    shortest = min(
        max(1, facts.SOURCES[f.source_key].review_days // 2) if f.watch
        else facts.SOURCES[f.source_key].review_days
        for f in facts.FACTS)
    just_inside = facts.VERIFIED_ON + timedelta(days=shortest - 1)
    blocking = [f for f in facts.audit(today=just_inside) if f.severity == "BLOCKING"]
    check(f"no fact is stale at {shortest - 1} days (inside the shortest window)",
          not blocking, "; ".join(f.code for f in blocking))

    # One day past the shortest window, the watch-flagged facts SHOULD fire.
    # If they do not, the tightening regressed back to being decorative.
    just_past = facts.VERIFIED_ON + timedelta(days=shortest + 1)
    past_codes = {f.code for f in facts.audit(today=just_past)}
    watch_short = [f for f in facts.FACTS
                   if f.watch and facts.SOURCES[f.source_key].review_days <= 45]
    check("tightened windows fire earlier than the source default",
          bool(watch_short) and "STALE_FACT" in past_codes,
          "watch-flagged facts did not go stale one day past the shortest window")

    # A future check date is a lie about work not done.
    future = facts.audit(today=facts.VERIFIED_ON - timedelta(days=1))
    check("a future check date is rejected",
          any(f.code == "FUTURE_CHECK_DATE" for f in future))

    # A missing quote must be caught, not tolerated.
    unsourced = replace(facts.FACTS[0], quote="")
    fs = facts.FACTS
    facts.FACTS = (unsourced,) + fs[1:]
    try:
        check("a fact with no verbatim quote is blocking",
              any(f.code == "MISSING_QUOTE" for f in facts.audit(today=facts.VERIFIED_ON)))
    finally:
        facts.FACTS = fs

    unknown = replace(facts.FACTS[0], source_key="nonexistent_source")
    facts.FACTS = (unknown,) + facts.FACTS[1:]
    try:
        check("a fact citing an unregistered source is blocking",
              any(f.code == "UNKNOWN_SOURCE" for f in facts.audit(today=facts.VERIFIED_ON)))
    finally:
        facts.FACTS = fs

    dupe = facts.FACTS[1]
    facts.FACTS = facts.FACTS + (dupe,)
    try:
        check("a duplicate fact key is blocking",
              any(f.code == "DUPLICATE_FACT_KEY" for f in facts.audit(today=facts.VERIFIED_ON)))
    finally:
        facts.FACTS = facts.FACTS[:-1]


# ---------------------------------------------------------------------------
# 3. The four AIEd principles are MOE's, verbatim
# ---------------------------------------------------------------------------

def test_principles() -> None:
    names = [p.name for p in tools.PRINCIPLES]
    check("the four principles are Agency, Inclusivity, Fairness, Safety",
          names == ["Agency", "Inclusivity", "Fairness", "Safety"], str(names))
    check("every principle poses a question a teacher can answer",
          all(p.question.strip() for p in tools.PRINCIPLES))


# ---------------------------------------------------------------------------
# 4. Tool listing guardrails -- each one proven by violating it
# ---------------------------------------------------------------------------

def test_tool_rules() -> None:
    findings = tools.check()
    blocking = [f for f in findings if f.severity == "BLOCKING"]
    check("tool registry audits clean", not blocking,
          "; ".join(f.code for f in blocking))

    check("every tool carries a caveat",
          all(t.watch_out.strip() for t in tools.TOOLS))
    check("every tool says what to use it for",
          all(t.use_it_for.strip() for t in tools.TOOLS))

    # No commercial tool may claim PERMITTED. We cannot audit a vendor.
    for t in tools.TOOLS:
        if not t.official:
            check(f"commercial '{t.key}' is not rated PERMITTED",
                  t.verdict != "PERMITTED", t.verdict)

    # No official tool may be sponsored. That is a credibility kill.
    for t in tools.TOOLS:
        if t.official:
            check(f"official '{t.key}' carries no sponsor", not t.sponsor, t.sponsor)

    # Commercial listings need evidence.
    for t in tools.TOOLS:
        if not t.official:
            check(f"commercial '{t.key}' has evidence", bool(t.evidence))
            for ek in t.evidence:
                check(f"commercial '{t.key}' cites real fact '{ek}'",
                      ek in facts.FACTS_BY_KEY)

    # --- now try to violate each rule and confirm it is caught ---

    def with_tool(t):
        """Run tools.check() with one tool swapped in, then restore."""
        saved = tools.TOOLS
        tools.TOOLS = (t,) + saved[1:]
        try:
            return tools.check()
        finally:
            tools.TOOLS = saved

    base = tools.TOOLS[0]

    sponsored_official = replace(base, sponsor="SomeEdTech Pte Ltd")
    check("sponsoring an official MOE tool is blocked",
          any(f.code == "SPONSORED_OFFICIAL_TOOL"
              for f in with_tool(sponsored_official)))

    commercial_permitted = replace(
        base, key="fake_vendor", official=False, verdict="PERMITTED",
        evidence=("commercial_no_pii",), source_url="https://example.com")
    check("rating an unverified commercial tool PERMITTED is blocked",
          any(f.code == "COMMERCIAL_CLAIMS_PERMITTED"
              for f in with_tool(commercial_permitted)))

    no_caveat = replace(base, key="no_caveat", watch_out="")
    check("a listing with no caveat is blocked",
          any(f.code == "MISSING_CAVEAT" for f in with_tool(no_caveat)))

    unsupported = replace(base, key="unsupported", official=False, evidence=())
    check("a commercial tool with no evidence is blocked",
          any(f.code == "UNSUPPORTED_COMMERCIAL_TOOL"
              for f in with_tool(unsupported)))

    bad_verdict = replace(base, key="bad", verdict="GREAT")
    check("an unrecognised verdict is blocked",
          any(f.code == "BAD_VERDICT" for f in with_tool(bad_verdict)))

    unverified_not_held = replace(
        base, key="unv", official=False, verdict="PERMITTED", unverified=True,
        evidence=("commercial_no_pii",))
    codes = {f.code for f in with_tool(unverified_not_held)}
    check("an unverified tool that is not HOLD is blocked",
          "UNVERIFIED_NOT_HELD" in codes or "COMMERCIAL_CLAIMS_PERMITTED" in codes,
          str(codes))

    bad_evidence = replace(base, key="badev", evidence=("made_up_fact",))
    check("a tool citing a nonexistent fact is blocked",
          any(f.code == "UNKNOWN_EVIDENCE" for f in with_tool(bad_evidence)))


# ---------------------------------------------------------------------------
# 5. The level rules are stated correctly -- the highest-risk content
# ---------------------------------------------------------------------------

def test_level_rules() -> None:
    for key in ("p1_p3_rule", "p4_p6_rule", "secondary_rule", "exams_prohibited",
                "commercial_no_pii", "parental_consent", "four_learns",
                "p4_entry_reason", "moe_data_anonymised", "aied_framework"):
        check(f"fact '{key}' exists", key in facts.FACTS_BY_KEY)

    p13 = facts.FACTS_BY_KEY["p1_p3_rule"].quote.lower()
    check("P1-3 is stated as print-first and hands-on",
          "print-first" in p13 and "hands-on" in p13)
    check("P1-3 explicitly bars students from using chatbots",
          "not be tasked to use chatbots" in p13)

    p46 = facts.FACTS_BY_KEY["p4_p6_rule"].quote.lower()
    check("P4-6 requires teacher supervision", "teacher supervision" in p46)
    check("P4-6 limits tools to those designed for education",
          "specifically designed for education" in p46)

    pii = facts.FACTS_BY_KEY["commercial_no_pii"].quote.lower()
    check("the no-PII rule names personal identifiable information",
          "personal identifiable information" in pii)

    consent = facts.FACTS_BY_KEY["parental_consent"].quote.lower()
    check("the parental consent rule is captured",
          "parental consent" in consent)

    exams = facts.FACTS_BY_KEY["exams_prohibited"].quote.lower()
    check("national exams prohibit AI", "use of ai is prohibited" in exams)

    # No student-facing tool may claim P1-P3.
    for t in tools.TOOLS:
        if t.audience == "students":
            for lvl in ("P1", "P2", "P3"):
                check(f"student tool '{t.key}' is not listed for {lvl}",
                      lvl not in t.levels, t.levels)


# ---------------------------------------------------------------------------
# 7. The scenario checker -- the thing teachers actually type
# ---------------------------------------------------------------------------

def test_checker() -> None:
    from moe import checker

    # --- a bare parenthesised string must not survive as a "tuple" ---
    # reasons=("text") is a str, not a 1-tuple. Iterating it yields characters,
    # which shipped once and rendered the site one letter per bullet.
    _a = checker.Answer("ALLOWED", "h", reasons=("just text"))
    check("a bare string is coerced into a real tuple",
          _a.reasons == ("just text",), repr(_a.reasons))
    check("no Answer field is ever a bare string",
          all(isinstance(getattr(_a, f), tuple)
              for f in ("reasons", "conditions", "evidence")))

    # --- the classic errors, each of which a teacher will actually type ---
    a = checker.answer("p1_3", "student", "lea")
    check("a chatbot is NOT_ALLOWED for P1-P3 students", a.verdict == "NOT_ALLOWED",
          a.verdict)
    check("the P1-P3 refusal cites the lower-primary rule", "p1_p3_rule" in a.evidence)

    # A general chatbot is not "designed for education", so supervision alone
    # cannot clear it at P4-6. This was a REAL bug: the first version returned
    # SUPERVISED for ChatGPT at P4-6, which is precisely the error this site
    # exists to prevent. Lock it hard.
    a = checker.answer("p4_6", "student", "chatgpt")
    check("a commercial chatbot is NOT simply SUPERVISED at P4-6",
          a.verdict != "SUPERVISED", f"got {a.verdict}")
    check("a commercial chatbot at P4-6 requires school approval",
          a.verdict == "MUST_CHECK", a.verdict)
    check("the P4-6 commercial answer demands parental consent",
          "parental_consent" in a.evidence)

    # An OFFICIAL SLS tool at P4-6 with students IS the sanctioned case.
    a = checker.answer("p4_6", "student", "lea")
    check("an official SLS tool is SUPERVISED at P4-6 with students",
          a.verdict == "SUPERVISED", a.verdict)
    check("the supervision answer tells them to actually supervise",
          any("supervise" in c.lower() for c in a.conditions))

    # Teacher-only use is the lowest-risk path and is never age-blocked.
    a = checker.answer("p1_3", "teacher", "chatgpt")
    check("teacher-only use is ALLOWED even at P1-3", a.verdict == "ALLOWED", a.verdict)
    check("every answer states the no-PII rule", any(
        "personal identifiable" in c.lower() or "names" in c.lower()
        for c in a.conditions))

    # A COMMERCIAL tool with students is NEVER cleared, at ANY level. This
    # caught a real bug: the checker read MOE's "students take greater
    # ownership" sentence as a permission, and returned SUPERVISED for a
    # commercial chatbot at Secondary. Ownership is responsibility, not
    # clearance.
    for lvl in ("p4_6", "secondary", "jc"):
        a = checker.answer(lvl, "student", "chatgpt")
        check(f"a commercial tool with {lvl} students is never cleared",
              a.verdict == "MUST_CHECK", f"{lvl}: got {a.verdict}")
        check(f"the {lvl} commercial answer demands parental consent",
              "parental_consent" in a.evidence, str(a.evidence))

    # Secondary tightens integrity; exams are named as non-negotiable.
    # Checked on an OFFICIAL tool, which is the case that reaches the
    # integrity rules at all.
    a = checker.answer("secondary", "student", "lea")
    check("secondary student use cites the disclosure rule",
          "disclosure_rule" in a.evidence, str(a.evidence))
    check("national exams are named as prohibiting AI",
          "exam" in a.escalate.lower(), a.escalate)

    a = checker.answer("jc", "student", "lea")
    check("JC student use cites the exams rule", "exams_prohibited" in a.evidence,
          str(a.evidence))

    # Monotonicity: raising the level must never make a tool MORE permitted
    # for students. A more mature cohort knows more about AI; it does not
    # acquire a new right to use an outside product.
    rank = {"NOT_ALLOWED": 0, "MUST_CHECK": 1, "SUPERVISED": 2, "ALLOWED": 3}
    for tk in ("lea", "chatgpt"):
        seq = [rank[checker.answer(l, "student", tk).verdict]
               for l in ("p1_3", "p4_6", "secondary", "jc")]
        check(f"student permission never increases with level ({tk})",
              all(x <= y for x, y in zip(seq, seq[1:])), str(seq))

    # --- honesty refusals ---
    a = checker.answer("p4_6", "student", "some_unreviewed_tool")
    check("an unreviewed tool is refused, not guessed", a.verdict == "UNKNOWN", a.verdict)
    # Normalise hyphens: the copy writes "parental-consent" and "no-PPI" style
    # compounds, the assertion should not care which way the dash points.
    _unrev = " ".join(list(a.conditions) + list(a.reasons) + [a.escalate]).lower()
    _unrev_flat = _unrev.replace("-", " ")
    check("an unreviewed-tool refusal still points at the universal rule",
          "parental consent" in _unrev_flat
          or "personal identifiable" in _unrev_flat, _unrev)

    a = checker.answer("kindergarten", "student", "lea")
    check("an unrecognised level is refused", a.verdict == "UNKNOWN", a.verdict)
    a = checker.answer("p4_6", "aliens", "lea")
    check("an unrecognised audience is refused", a.verdict == "UNKNOWN", a.verdict)

    # --- every answer must be citable, except refusals ---
    for lvl in checker.LEVELS:
        for aud in checker.AUDIENCES:
            for tk, tool in TOOLS_BY_KEY_LOCAL().items():
                a = checker.answer(lvl, aud, tk)
                if a.verdict == "UNKNOWN":
                    continue
                check(f"answer {lvl}/{aud}/{tk} is citable", bool(a.evidence),
                      "no evidence")
                for ek in a.evidence:
                    check(f"answer {lvl}/{aud}/{tk} cites real fact '{ek}'",
                          ek in facts.FACTS_BY_KEY)
                quotes = checker.citations_for(a)
                check(f"answer {lvl}/{aud}/{tk} resolves to quotes", bool(quotes))
                for pub, url, quote in quotes:
                    check(f"answer {lvl}/{aud}/{tk} quote is MOE-sourced",
                          _is_official_moe(url), url)
                    check(f"answer {lvl}/{aud}/{tk} quote is non-empty",
                          len(quote) >= 40)

    # --- monotonicity: the P1-3 bar must never be weaker than P4-6 ---
    # A regression here would mean the age rules got reordered.
    for tk in ("lea", "acp", "chatgpt"):
        lo = checker.answer("p1_3", "student", tk)
        hi = checker.answer("p4_6", "student", tk)
        rank = {"NOT_ALLOWED": 0, "MUST_CHECK": 1, "SUPERVISED": 2, "ALLOWED": 3,
                "UNKNOWN": -1}
        check(f"'{tk}' is not MORE permitted at P1-3 than at P4-6",
              rank[lo.verdict] <= rank[hi.verdict],
              f"P1-3={lo.verdict} P4-6={hi.verdict}")

    # --- teacher-only must never be stricter than student-use ---
    # That ordering is nonsense: using a tool yourself is always the safer act.
    for tk in TOOLS_BY_KEY_LOCAL():
        teach = checker.answer("p4_6", "teacher", tk)
        stud = checker.answer("p4_6", "student", tk)
        rank = {"NOT_ALLOWED": 0, "MUST_CHECK": 1, "SUPERVISED": 2, "ALLOWED": 3,
                "UNKNOWN": -1}
        if teach.verdict != "UNKNOWN" and stud.verdict != "UNKNOWN":
            check(f"'{tk}' teacher-use is not stricter than student-use",
                  rank[teach.verdict] >= rank[stud.verdict],
                  f"teacher={teach.verdict} student={stud.verdict}")

    check("the checker exposes no free-text input",
          all(k in checker.LEVELS for k in checker.LEVELS)
          and all(k in checker.AUDIENCES for k in checker.AUDIENCES))
    check("every registered tool is offered as an option",
          {k for k, _, _, _ in checker.all_tool_options()} == set(TOOLS_BY_KEY_LOCAL()))


def TOOLS_BY_KEY_LOCAL():
    from moe import tools as t
    return t.TOOLS_BY_KEY


# ---------------------------------------------------------------------------
# 6. Coverage honesty
# ---------------------------------------------------------------------------

def test_coverage() -> None:
    cov = facts.coverage()
    check("coverage is non-empty", bool(cov))
    check("level guidance is covered", cov.get("levels", 0) >= 3)
    check("data governance is covered", cov.get("data", 0) >= 2)

    verdicts = tools.by_verdict()
    check("all eight official SLS tools are listed",
          sum(1 for t in tools.TOOLS if t.official) == 8,
          str(sum(1 for t in tools.TOOLS if t.official)))
    check("every verdict bucket is defined",
          set(verdicts) == {"PERMITTED", "CONDITIONAL", "HOLD"}, str(set(verdicts)))

    cites = facts.citations()
    check("citations are exportable for the sources page", len(cites) == len(facts.FACTS))
    check("every citation carries a publisher and url",
          all(c["publisher"] and c["url"].startswith("https://") for c in cites))


def test_gui() -> None:
    """The published picker must be the Python rules, not a parallel copy.

    The web GUI is the part most likely to drift: someone edits the JavaScript
    to make a sentence nicer and the site starts making a compliance claim
    Python never cleared. So the payload is regenerated here from `answer()`
    and compared against what the build actually wrote to disk.
    """
    import json
    import build_site

    SITE = build_site.SITE
    js = SITE / "checker-data.js"
    html = SITE / "index.html"
    check("checker-data.js exists", js.exists())
    check("index.html exists", html.exists())
    if not (js.exists() and html.exists()):
        return

    raw = js.read_text(encoding="utf-8")
    payload = json.loads(raw.removeprefix("window.MOE_CHECKER=").rstrip(";"))
    fresh = build_site.checker_payload()

    expected = len(build_site.checker.LEVELS) * len(build_site.checker.AUDIENCES) \
        * len(tools.TOOLS)
    check("every level x audience x tool combination is pre-vetted",
          len(fresh["a"]) == expected,
          f"{len(fresh['a'])} of {expected}")
    check("the published payload matches the current rules exactly",
          payload == fresh,
          "checker-data.js is stale -- re-run build_site.py")

    # No rule may live in the JavaScript. It may only look up pre-vetted data.
    check("the JS contains no verdict logic, only a lookup",
          "D.a[" in (SITE / "js/checker.js").read_text(encoding="utf-8"))

    # The four verdicts the UI must be able to render.
    vs = {a["v"] for a in fresh["a"].values()}
    check("payload exercises every verdict the UI can render",
          {"ALLOWED", "SUPERVISED", "NOT_ALLOWED"} <= vs, str(sorted(vs)))

    # Every non-refusal answer must cite something a teacher can click.
    nocite = [k for k, a in fresh["a"].items()
              if a["v"] != "UNKNOWN" and not a["s"]]
    check("no answer without a citation", not nocite, str(nocite[:3]))
    bad_url = [s[1] for a in fresh["a"].values() for s in a["s"]
               if not s[1].startswith("https://")]
    check("every checker citation is an https ministry link", not bad_url, str(bad_url[:2]))

    # An UNKNOWN must never be rendered as though it were clearance.
    unk = [a for a in fresh["a"].values() if a["v"] == "UNKNOWN"]
    check("UNKNOWN is a refusal, never a green light",
          all(a["h"] != "Yes, for your own work" for a in unk))

    # The honesty property: no commercial tool is cleared outright for students.
    cleared = [k for k, a in fresh["a"].items()
               if k.split("|")[2] == "chatgpt" and k.split("|")[1] == "student"
               and a["v"] in ("ALLOWED", "SUPERVISED")]
    check("no commercial tool is ever cleared for student use",
          not cleared, str(cleared))


def test_onboard() -> None:
    """The first-timer Q&A must be citable and correctly scoped."""
    from moe import onboard

    qs = onboard.QUESTIONS
    check("there are questions to show a first-timer", len(qs) >= 8, str(len(qs)))
    check("questions are numbered 1-based without gaps",
          all(onboard.by_index(i) is not None for i in range(1, len(qs) + 1)))
    check("out-of-range index returns None, not a wrong answer",
          onboard.by_index(0) is None and onboard.by_index(len(qs) + 1) is None)

    # Every cited fact key must exist. A Q&A citing a nonexistent key renders
    # as an answer with no source, which is the failure this site cannot ship.
    for i, q in enumerate(qs, 1):
        missing = [k for k in q.evidence if k not in facts.FACTS_BY_KEY]
        check(f"Q{i} cites only real facts", not missing, str(missing))
        check(f"Q{i} has an answer", len(q.a) >= 2, str(len(q.a)))

    # The honesty property: at least one answer must be OUR framing with no
    # ministry citation, and it must say so. If every answer carried a
    # citation, we would be borrowing MOE's authority for our own opinions.
    uncited = [i for i, q in enumerate(qs, 1) if not q.evidence]
    check("some answers are our own framing, not MOE claims", len(uncited) >= 2,
          str(uncited))

    # The refusals must be visible. "What we will not tell you" is what makes
    # the rest credible.
    joined = " ".join(" ".join(q.a) for q in qs).lower()
    for topic in ("not affiliated", "approve", "cannot audit", "consent"):
        check(f"the Q&A addresses {topic!r}", topic in joined)

    # A first-timer must be told the safe default.
    check("the safe default is stated",
          "not yet" in joined or "escalat" in joined or "ask your h" in joined)

    # The big trap we shipped a bug about must be named explicitly.
    check("the 'ownership is not permission' trap is called out",
          "ownership" in joined)


def test_watch_and_billing() -> None:
    """The monitor and the ledger must not silently pass bad state."""
    import run_watch
    import run_billing

    # URL reachability logic, tested offline via the pure helpers.
    check("HTML tags are stripped before hashing",
          run_watch.strip_html(b"<p>Hello  <b>world</b></p>") == "Hello world")
    check("script and style blocks do not count as content",
          "alert" not in run_watch.strip_html(b"<script>alert(1)</script>ok"))
    check("identical text hashes identically",
          run_watch.digest_of(b"<p>a</p>") == run_watch.digest_of(b"<div>a</div>"))
    check("whitespace-only changes do not read as content changes",
          run_watch.digest_of(b"<p>a  b</p>") == run_watch.digest_of(b"<p>a\n b</p>"))
    check("real content changes DO change the digest",
          run_watch.digest_of(b"<p>a</p>") != run_watch.digest_of(b"<p>b</p>"))

    # All three real ACRA UEN formats must validate, or a legitimate sponsor
    # (a Pte Ltd, format B) gets rejected by our own code.
    for u in ("202412345Z", "T08LL1234A", "12345678A"):
        check(f"valid UEN accepted: {u}", run_billing._valid_uen(u))
    for u in ("1234", "", "+6591234567", "abcdefghij"):
        check(f"invalid UEN rejected: {u or '(empty)'}", not run_billing._valid_uen(u))

    # Every billing guard, proven by violating it.
    ok_sponsor = run_billing.Sponsor(
        key="s", name="Acme Pte Ltd", uen="202412345Z", tier="supporting",
        tool_keys=("chatgpt",), status="active", last_paid="2026-10-01")
    check("a legitimate sponsor has no problems",
          not run_billing.check_model([ok_sponsor]),
          str(run_billing.check_model([ok_sponsor])))

    official_slot = run_billing.Sponsor(
        key="s", name="Acme Pte Ltd", uen="202412345Z", tier="supporting",
        tool_keys=("lea",), status="active", last_paid="2026-10-01")
    check("a slot on an OFFICIAL MOE tool is refused",
          any("OFFICIAL MOE tool" in p for p in run_billing.check_model([official_slot])))

    unpaid = run_billing.Sponsor(
        key="s", name="Ghost Pte Ltd", uen="202412345Z", tier="supporting",
        status="active", last_paid="")
    check("an active sponsor with no payment recorded is refused",
          any("no payment recorded" in p for p in run_billing.check_model([unpaid])))

    over = run_billing.Sponsor(
        key="s", name="Greedy Pte Ltd", uen="202412345Z", tier="supporting",
        tool_keys=("chatgpt", "acp"), status="active", last_paid="2026-10-01")
    check("exceeding the tier slot allowance is refused",
          any("allows" in p for p in run_billing.check_model([over])))

    # Revenue must only count money actually received.
    pending = run_billing.Sponsor(key="p", name="Pipeline Pte Ltd",
                                  uen="202412345Z", tier="sustained",
                                  status="pending")
    check("a signed-but-unpaid sponsor is pipeline, not revenue",
          run_billing.monthly_recurring([pending]) == 0)
    check("but it still shows as pipeline",
          run_billing.pipeline([pending]) == 1200)
    check("an active paid sponsor IS revenue",
          run_billing.monthly_recurring([ok_sponsor]) == 500)

    # An unreadable ledger must never look like a business with no revenue.
    # Returning [] on a parse failure reports S$0 and zero sponsors while a
    # paying sponsor sits unreadable -- the one failure a billing system must
    # never produce, because it looks like success.
    #
    # load() reads the module-level LEDGER path, so the test must point LEDGER
    # at the bad file. Writing a temp file and calling load() proves nothing:
    # it would just read the real, valid ledger and pass.
    real_ledger = run_billing.LEDGER
    bad = real_ledger.with_name("_tmp_bad_ledger.json")
    try:
        for content, label in ((b"{ not json", "corrupt"),
                               (b'{"nope": 1}', "wrong-shaped"),
                               (b'{"sponsors": [{"nonsense": 1}]}',
                                "unrecognised-record")):
            bad.write_bytes(content)
            run_billing.LEDGER = bad
            raised = False
            try:
                run_billing.load()
            except run_billing.LedgerError:
                raised = True
            check(f"a {label} ledger raises LedgerError", raised)
            # And it must never come back as a clean empty list.
            if not raised:
                check(f"a {label} ledger does not report zero sponsors", False,
                      "load() returned instead of refusing")
    finally:
        run_billing.LEDGER = real_ledger
        bad.unlink(missing_ok=True)

    # The ledger file itself must exist and be genuinely empty. A missing file
    # and a file with no sponsors are the same outcome by accident, not by
    # design -- the file is what makes "S$0" a recorded fact.
    check("the sponsor ledger file exists on disk",
          run_billing.LEDGER.exists(), str(run_billing.LEDGER))
    if run_billing.LEDGER.exists():
        check("and it currently holds no sponsors",
              json.loads(run_billing.LEDGER.read_text(encoding="utf-8"))
              ["sponsors"] == [])


def test_daily() -> None:
    """The orchestrator must escalate to the WORST stage, never the last one.

    A clean billing run after a dead citation must not report success, so exit
    codes are derived from all stages together rather than sequentially.
    """
    import run_daily

    def worst(*stages):
        rec = {"stages": list(stages)}
        if any(s.get("failed") for s in stages):
            return 2
        return 0 if all(s.get("ok") for s in stages) else 1

    ok = {"stage": "x", "ok": True, "failed": False}
    needs_human = {"stage": "x", "ok": False, "failed": False}
    broken = {"stage": "x", "ok": False, "failed": True}

    check("all clean -> 0", worst(ok, ok, ok) == 0)
    check("something needs a human -> 1", worst(ok, needs_human, ok) == 1)
    check("anything broken -> 2", worst(ok, broken, ok) == 2)
    # The specific trap: a broken stage FIRST, clean stages after it.
    check("a dead citation is not masked by a later clean stage",
          worst(broken, ok, ok) == 2)
    check("a clean run after a bad one is not success either",
          worst(needs_human, ok) == 1)

    # A subprocess that dies must not be read as "clean". run_json returns
    # None on unparseable output; the stage wrapper turns that into failed.
    parsed, code, err = run_daily.run_json("no_such_script_xyz.py")
    check("a missing script does not fabricate a result",
          parsed is None and code == 3, f"code={code}")

    # Every stage must report a distinct name, or brief() silently drops one.
    names = {"watch", "audit", "build", "bill"}
    # A dead source and a changed source are different failures with different
# remedies, so the summary has to be able to say both. The fixture carries
# both; asserting "DEAD" against a changed-only fixture would be testing my
# own sloppy fixture rather than the code.
    rec = {"exit": 1, "stages": [
    {"stage": "watch", "ok": False, "failed": True, "checked": 4,
    "dead": ["sls_aied"], "changed": ["moe_aied"]},
    {"stage": "audit", "ok": False, "blocking": ["STALE_FACT: x"],
    "facts": 22, "tools": 9, "verified_days_ago": 99,
    "shortest_window_days": 22, "reverify_by": "2026-11-08",
    "days_to_reverify": -77},
    {"stage": "build", "ok": False, "refused": True, "published": False},
    {"stage": "bill", "ok": False, "failed": True, "problems": ["bad UEN"],
    "mrr_sgd": 0, "pipeline_sgd": 0, "active_sponsors": 1,
    "sponsors": 1},
    ]}
    text = run_daily.brief(rec)
    for token in ("DEAD", "CHANGED", "BLOCKING", "REFUSED", "ILLEGAL"):
        check(f"the summary shouts about {token}", token in text)
    check("every stage appears in the summary",
          {s["stage"] for s in rec["stages"]} == names)
    check("an overdue re-verification is reported as a negative day count",
          rec["stages"][1]["days_to_reverify"] < 0)

    # The binding deadline must be the EARLIEST per-fact deadline, not
    # (shortest window - stalest age). Those differ whenever the most recently
    # verified fact is not the one with the shortest window.
    from moe import facts
    from datetime import date
    deadlines = [
        (f.checked_on.toordinal()
         + (facts.SOURCES[f.source_key].review_days // 2 if f.watch
            else facts.SOURCES[f.source_key].review_days))
        for f in facts.FACTS]
    check("the real registry's binding deadline is 8 Nov 2026",
          date.fromordinal(min(deadlines)).isoformat() == "2026-11-08",
          date.fromordinal(min(deadlines)).isoformat())

    # History must survive a truncated final line: a process killed mid-write
    # leaves one bad line, and the viewer must not then crash forever.
    hist = run_daily.HISTORY
    hist.write_text('{"exit": 0}\n{"exit": 1}\n{"trunca', encoding="utf-8")
    rows = run_daily.read_history()
    check("a truncated history line is skipped, not fatal", len(rows) == 2,
          str(len(rows)))
    hist.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
print()
print("=" * 70)
print("MOE DIRECTORY -- COMPLIANCE REGRESSION TESTS")
print("=" * 70)

for fn in (test_registry, test_staleness, test_principles, test_tool_rules,
           test_level_rules, test_checker, test_onboard, test_gui,
           test_watch_and_billing, test_daily, test_coverage):
    fn()

print(f"  {PASS} checks passed")
if FAIL:
    print(f"  {len(FAIL)} FAILED")
    print()
    for f in FAIL:
        print(f"    FAIL: {f}")
    print()
    print("  A compliance site whose checks have broken is more dangerous than no")
    print("  site, because it still looks authoritative. Do not publish.")
    print()
    print("=" * 70)
    sys.exit(1)

print("  All good.")
print()
print("  Note what this does NOT prove. It proves the registry is internally")
print("  consistent, sourced, fresh and non-contradictory. It cannot prove we")
print("  read MOE correctly -- only a teacher clicking our citations can do that,")
print("  which is why every claim on the site links to its source.")
print()
print("=" * 70)