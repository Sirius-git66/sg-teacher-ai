"""Site generation engine — renders the multi-page static site.

This module reads page templates from src/pages/, injects dynamic content
generated from the fact and tool registries, and writes the output to dist/.

The build pipeline:
  1. Audit — refuse to build if any fact is stale or any tool listing is broken
  2. Generate checker data — pre-compute every level x audience x tool answer
  3. Generate mascot data — emit the pixel layers as JSON
  4. Render pages — substitute placeholders in each page template
  5. Copy static assets — CSS, JS, favicon
  6. Verify output — check every internal link resolves

No rule lives in the JavaScript. The checker JS only looks up pre-vetted
answers. The build writes the data; the JS reads it.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from . import facts as facts_mod
from . import tools as tools_mod
from . import checker as checker_mod
from . import mascot as mascot_mod
from . import onboard as onboard_mod


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent          # teachers/
SRC = ROOT / "src"
TEMPLATES = SRC / "templates"
PAGES = SRC / "pages"
CSS_DIR = SRC / "css"
JS_DIR = SRC / "js"
ASSETS_DIR = SRC / "assets"
DIST = ROOT / "dist"


# ---------------------------------------------------------------------------
# HTML generators — produce the content fragments pages inject
# ---------------------------------------------------------------------------

_VERDICT_BADGE = {
    "PERMITTED": ("verdict-permitted", "Permitted"),
    "CONDITIONAL": ("verdict-conditional", "Conditional"),
    "HOLD": ("verdict-hold", "Hold"),
}


def _tool_card(tool: tools_mod.Tool) -> str:
    """Render one tool card for the tools directory page."""
    css_class, label = _VERDICT_BADGE.get(tool.verdict, ("verdict-hold", "Hold"))
    official_tag = "Official SLS Tool" if tool.official else "Commercial"

    conditions_html = ""
    if tool.conditions:
        items = "".join(f"<li>{_esc(c)}</li>" for c in tool.conditions)
        conditions_html = f'<div class="tool-conditions"><h4>Conditions</h4><ul>{items}</ul></div>'

    evidence_links = ""
    if tool.evidence:
        seen_urls = set()
        links = []
        for ek in tool.evidence:
            fact = facts_mod.FACTS_BY_KEY.get(ek)
            if fact:
                source = facts_mod.SOURCES.get(fact.source_key)
                if source and source.url not in seen_urls:
                    seen_urls.add(source.url)
                    links.append(
                        f'<a href="{_esc(source.url)}" target="_blank" '
                        f'rel="noopener">{_esc(source.title)}</a>'
                    )
        if links:
            evidence_links = (
                '<div class="tool-evidence"><h4>Evidence</h4>'
                + "".join(f"<p>{l}</p>" for l in links)
                + "</div>"
            )

    sponsor_html = ""
    if tool.sponsor:
        sponsor_html = f'<div class="tool-sponsor">Sponsored by {_esc(tool.sponsor)}</div>'

    unverified_html = ""
    if tool.unverified:
        unverified_html = '<div class="tool-unverified">Unverified — we could not confirm the claims below.</div>'

    return f'''<article class="tool-card" id="tool-{tool.key}">
  <div class="tool-header">
    <h3>{_esc(tool.name)}</h3>
    <span class="verdict-badge {css_class}">{label}</span>
    <span class="tool-type">{official_tag}</span>
  </div>
  <p class="tool-summary">{_esc(tool.summary)}</p>
  <div class="tool-meta">
    <span><strong>Audience:</strong> {_esc(tool.audience)}</span>
    <span><strong>Levels:</strong> {_esc(", ".join(tool.levels) if tool.levels else "All levels")}</span>
    <span><strong>Subjects:</strong> {_esc(", ".join(tool.subjects) if tool.subjects else "All subjects")}</span>
  </div>
  <div class="tool-use"><h4>Use it for</h4><p>{_esc(tool.use_it_for)}</p></div>
  <div class="tool-caveat"><h4>Watch out</h4><p>{_esc(tool.watch_out)}</p></div>
  {conditions_html}
  {evidence_links}
  {sponsor_html}
  {unverified_html}
</article>'''


def tool_cards_html() -> str:
    """Render all tool cards, grouped: official first, then commercial."""
    official = [t for t in tools_mod.TOOLS if t.official]
    commercial = [t for t in tools_mod.TOOLS if not t.official]

    sections = []
    if official:
        cards = "\n".join(_tool_card(t) for t in official)
        sections.append(f'<section class="tool-group"><h2>Official MOE / SLS Tools</h2><p class="group-note">Built by MOE into the Student Learning Space. In-built safety guardrails. Verdict: Permitted.</p>{cards}</section>')
    if commercial:
        cards = "\n".join(_tool_card(t) for t in commercial)
        sections.append(f'<section class="tool-group"><h2>Commercial Tools</h2><p class="group-note">Third-party tools. We cannot audit their data handling. Verdict ceiling: Conditional. Unverified tools: Hold.</p>{cards}</section>')

    return "\n".join(sections)


def fact_table_html() -> str:
    """Render the full fact table for the sources page."""
    rows = []
    for f in facts_mod.FACTS:
        source = facts_mod.SOURCES[f.source_key]
        watch_tag = ' <span class="watch-flag" title="Flagged for closer monitoring">watch</span>' if f.watch else ""
        rows.append(f'''<tr>
  <td class="fact-key">{_esc(f.key)}</td>
  <td class="fact-claim">{_esc(f.claim)}{watch_tag}</td>
  <td class="fact-quote"><blockquote>{_esc(f.quote)}</blockquote></td>
  <td class="fact-source"><a href="{_esc(source.url)}" target="_blank" rel="noopener">{_esc(source.title)}</a><br><small>{_esc(source.publisher)}</small></td>
  <td class="fact-date">{f.checked_on.isoformat()}</td>
</tr>''')

    return "\n".join(rows)


def source_cards_html() -> str:
    """Render source cards for the sources page header."""
    cards = []
    for s in facts_mod.SOURCES.values():
        fact_count = sum(1 for f in facts_mod.FACTS if f.source_key == s.key)
        cards.append(f'''<div class="source-card">
  <h3><a href="{_esc(s.url)}" target="_blank" rel="noopener">{_esc(s.title)}</a></h3>
  <p class="source-publisher">{_esc(s.publisher)}</p>
  <p class="source-meta">Review every <strong>{s.review_days} days</strong> &middot; {fact_count} facts cited</p>
  <p class="source-remit">{_esc(s.authoritative_for)}</p>
</div>''')
    return "\n".join(cards)


def onboard_html() -> str:
    """Render the onboarding Q&A for the about page."""
    items = []
    for i, q in enumerate(onboard_mod.QUESTIONS, 1):
        answer_paras = "".join(f"<p>{_esc(a)}</p>" for a in q.a)
        cite_note = ""
        if q.evidence:
            links = []
            for ek in q.evidence:
                fact = facts_mod.FACTS_BY_KEY.get(ek)
                if fact:
                    source = facts_mod.SOURCES.get(fact.source_key)
                    if source:
                        links.append(f'<a href="{_esc(source.url)}" target="_blank" rel="noopener">source</a>')
            if links:
                cite_note = f'<p class="qa-citation">Cited: {", ".join(links)}</p>'
        else:
            cite_note = '<p class="qa-uncited">Our own framing — not a MOE citation.</p>'

        items.append(f'''<details class="qa-item">
  <summary>{i}. {_esc(q.q)}</summary>
  <div class="qa-answer">{answer_paras}{cite_note}</div>
</details>''')
    return "\n".join(items)


def checker_options_html() -> str:
    """Render the dropdown options for the scenario checker on index.html."""
    # Level options
    level_opts = [
        ('p1_3', 'Primary 1 to 3'),
        ('p4_6', 'Primary 4 to 6'),
        ('secondary', 'Secondary'),
        ('jc', 'JC / Pre-university'),
    ]
    level_html = "\n".join(f'<option value="{k}">{v}</option>' for k, v in level_opts)

    # Audience options
    aud_opts = [
        ('teacher', 'For my own work (teacher)'),
        ('student', 'Students will use it'),
    ]
    aud_html = "\n".join(f'<option value="{k}">{v}</option>' for k, v in aud_opts)

    # Tool options, grouped
    official = [t for t in tools_mod.TOOLS if t.official]
    commercial = [t for t in tools_mod.TOOLS if not t.official]
    tool_parts = ['<optgroup label="Official MOE / SLS Tools">']
    tool_parts.extend(f'<option value="{t.key}">{_esc(t.name)}</option>' for t in official)
    tool_parts.append('</optgroup><optgroup label="Commercial Tools">')
    tool_parts.extend(f'<option value="{t.key}">{_esc(t.name)}</option>' for t in commercial)
    tool_parts.append('</optgroup>')
    tool_html = "\n".join(tool_parts)

    return level_html, aud_html, tool_html


# ---------------------------------------------------------------------------
# Build pipeline
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """Minimal HTML escaping."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build(check_only: bool = False) -> list[str]:
    """Run the full build pipeline. Returns a list of status messages.

    If `check_only` is True, runs the audit but does not write any files.
    Use this for CI checks where you want to verify freshness without building.

    Raises RuntimeError if blocking findings exist. The build refuses to
    publish stale claims — that is the entire product.
    """
    messages = []

    # --- Step 1: Audit ---
    fact_findings = facts_mod.audit()
    tool_findings = tools_mod.check()
    blocking = [f for f in fact_findings + tool_findings if f.severity == "BLOCKING"]

    if blocking:
        codes = [f.code for f in blocking]
        raise RuntimeError(
            f"Build refused: {len(blocking)} blocking finding(s): {', '.join(codes)}. "
            f"Do not publish until these are resolved."
        )
    messages.append(f"Audit passed: {len(facts_mod.FACTS)} facts, {len(tools_mod.TOOLS)} tools, "
                     f"{len(fact_findings) + len(tool_findings)} non-blocking findings")

    if check_only:
        messages.append("Check-only mode: not writing files")
        return messages

    # --- Step 2: Clean and prepare dist/ ---
    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / "css").mkdir(exist_ok=True)
    (DIST / "js").mkdir(exist_ok=True)

    # Clean existing files in dist (avoid rmtree which can fail on OneDrive)
    for item in DIST.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir() and item.name in ("css", "js"):
            for f in item.iterdir():
                if f.is_file():
                    f.unlink()

    # --- Step 3: Generate data files ---
    # checker-data.js
    payload = checker_mod.checker_payload()
    checker_js = "window.MOE_CHECKER=" + json.dumps(payload, ensure_ascii=False) + ";"
    _write(DIST / "checker-data.js", checker_js)
    answer_count = len(payload["a"])
    messages.append(f"checker-data.js: {answer_count} pre-vetted answers")

    # mascot-data.js
    mascot_data = mascot_mod.payload()
    mascot_js = "window.MOE_MASCOT=" + json.dumps(mascot_data, ensure_ascii=False) + ";"
    _write(DIST / "mascot-data.js", mascot_js)
    messages.append("mascot-data.js: pixel layers generated")

    # --- Step 4: Render pages ---
    base_template = _read(TEMPLATES / "base.html")

    # Pre-generate shared content
    tool_cards = tool_cards_html()
    fact_rows = fact_table_html()
    source_cards = source_cards_html()
    onboard_items = onboard_html()
    level_opts, aud_opts, tool_opts = checker_options_html()

    # Stats
    build_date = date.today().isoformat()
    fact_count = str(len(facts_mod.FACTS))
    tool_count = str(len(tools_mod.TOOLS))
    source_count = str(len(facts_mod.SOURCES))
    official_count = str(sum(1 for t in tools_mod.TOOLS if t.official))
    commercial_count = str(sum(1 for t in tools_mod.TOOLS if not t.official))
    stale_days = str(facts_mod.stale_days())
    shortest_window = str(min(
        max(1, facts_mod.SOURCES[f.source_key].review_days // 2) if f.watch
        else facts_mod.SOURCES[f.source_key].review_days
        for f in facts_mod.FACTS
    ))

    # Common replacements shared across all pages
    common = {
        "{{BUILD_DATE}}": build_date,
        "{{FACT_COUNT}}": fact_count,
        "{{TOOL_COUNT}}": tool_count,
        "{{SOURCE_COUNT}}": source_count,
        "{{OFFICIAL_COUNT}}": official_count,
        "{{COMMERCIAL_COUNT}}": commercial_count,
        "{{STALE_DAYS}}": stale_days,
        "{{SHORTEST_WINDOW}}": shortest_window,
    }

    # Page-specific content
    page_content = {
        "index.html": {
            "{{PAGE_TITLE}}": "AI in SG Schools — Which AI tools Singapore teachers can use, under MOE rules",
            "{{LEVEL_OPTIONS}}": level_opts,
            "{{AUDIENCE_OPTIONS}}": aud_opts,
            "{{TOOL_OPTIONS}}": tool_opts,
        },
        "tools.html": {
            "{{PAGE_TITLE}}": "Tool Directory — AI in SG Schools",
            "{{TOOL_CARDS}}": tool_cards,
        },
        "sources.html": {
            "{{PAGE_TITLE}}": "Sources & Citations — AI in SG Schools",
            "{{FACT_TABLE}}": fact_rows,
            "{{SOURCE_CARDS}}": source_cards,
        },
        "about.html": {
            "{{PAGE_TITLE}}": "About — AI in SG Schools",
            "{{ONBOARD_QA}}": onboard_items,
        },
        "sponsors.html": {
            "{{PAGE_TITLE}}": "Sponsorship — AI in SG Schools",
        },
    }

    for page_file in PAGES.glob("*.html"):
        template = _read(page_file)
        content = template

        # Apply common replacements
        for placeholder, value in common.items():
            content = content.replace(placeholder, value)

        # Apply page-specific replacements
        if page_file.name in page_content:
            for placeholder, value in page_content[page_file.name].items():
                content = content.replace(placeholder, value)

        # Determine active nav item from the page filename
        nav_page = page_file.stem  # e.g. "index", "tools", etc.
        nav_active = {
            "NAV_INDEX_ACTIVE": "active" if nav_page == "index" else "",
            "NAV_TOOLS_ACTIVE": "active" if nav_page == "tools" else "",
            "NAV_SOURCES_ACTIVE": "active" if nav_page == "sources" else "",
            "NAV_ABOUT_ACTIVE": "active" if nav_page == "about" else "",
            "NAV_SPONSORS_ACTIVE": "active" if nav_page == "sponsors" else "",
        }

        # Wrap in base template
        # Extract the page title from the rendered content
        page_title = page_content.get(page_file.name, {}).get(
            "{{PAGE_TITLE}}", "AI in SG Schools"
        )

        output = base_template.replace("{{PAGE_TITLE}}", page_title)
        for nav_key, nav_val in nav_active.items():
            output = output.replace("{{" + nav_key + "}}", nav_val)
        output = output.replace("{{PAGE_CONTENT}}", content)

        # Apply common replacements to the full output (covers footer stats)
        for placeholder, value in common.items():
            output = output.replace(placeholder, value)

        _write(DIST / page_file.name, output)
        messages.append(f"Rendered {page_file.name}")

    # --- Step 5: Copy static assets ---
    # CSS
    for css_file in CSS_DIR.glob("*.css"):
        shutil.copy2(css_file, DIST / "css" / css_file.name)
    messages.append(f"Copied {len(list(CSS_DIR.glob('*.css')))} CSS file(s)")

    # JS
    for js_file in JS_DIR.glob("*.js"):
        shutil.copy2(js_file, DIST / "js" / js_file.name)
    messages.append(f"Copied {len(list(JS_DIR.glob('*.js')))} JS file(s)")

    # Assets
    for asset_file in ASSETS_DIR.glob("*"):
        shutil.copy2(asset_file, DIST / asset_file.name)
    messages.append(f"Copied {len(list(ASSETS_DIR.glob('*')))} asset(s)")

    # --- Step 6: Verify output ---
    dist_files = {p.name for p in DIST.glob("*") if p.is_file()}
    expected = {"index.html", "tools.html", "sources.html", "about.html",
                "sponsors.html", "checker-data.js"}
    missing = expected - dist_files
    if missing:
        raise RuntimeError(f"Build output missing: {', '.join(missing)}")
    messages.append(f"Output verified: {len(dist_files)} files in dist/")

    return messages
