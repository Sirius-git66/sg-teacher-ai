# Project 2 — Singapore teacher MOE AI directory

## Operating guide (no technical background required)

Written for you. Every command is copy-paste. **You never edit any of these  
files** — if something needs changing, tell me and I do it.

---

## 1. What this actually is

A reference site for Singapore teachers answering one question: **"what can I  
actually use, at my level, under MOE rules?"**

Everyone else publishes lists. The problem with lists is that they go quietly  
wrong. MOE adds tools, shifts boundaries, and the list keeps claiming things that  
are no longer true. Nobody notices, because a well-formatted list looks  
authoritative whether or not it is.

So the thing I built is not really a website. It is a **fact-checking machine  
that generates a website**. The site cannot be published if any of its claims have  
gone stale.

---

## 2. The one idea worth understanding

Everything on the site traces back to one of **22 claims**, and each claim stores:

- the **verbatim quote** from MOE (not my paraphrase — paraphrase is where  
  compliance errors hide)
- the **URL** you can click
- the **date** someone last read it
- a **review window** based on how fast that source changes

Each source has its own window:

| Source                         | Re-verify every | Why                                     |
| ------------------------------ | --------------- | --------------------------------------- |
| SLS AI features page           | 45 days         | New tools ship often                    |
| MOE's AI-in-education position | 60 days         | Policy page, moves slowly               |
| AIEd Framework                 | 90 days         | Principles are stable                   |
| Parliamentary reply, May 2026  | 90 days         | A snapshot; superseded by newer replies |

Some claims are flagged as **"watch these"** — meaning they're the ones MOE has  
promised to expand, like ALS adding more subjects. Those get **half** their  
source's window, so a fact MOE said would grow is checked twice as often.

> **If a fact passes its window, the build fails and nothing is published.**  
> I proved this: I set every check date back seven months, ran the build, and it  
> refused with exit code 1 and refused to write the page.

---

## 3. Commands

```
cd C:\Users\FM\WorkBuddy\2026-10-17-13-03-18\project2_moe_ai
```

| Command                        | What it does                                     |
| ------------------------------ | ------------------------------------------------ |
| `python build_site.py`         | Audits everything, then writes `site/index.html` |
| `python build_site.py --check` | Audits only, writes nothing                      |
| `python test_moe.py`           | 760 checks on the compliance logic               |
| `node test_widget.js`          | Checks the on-page checker actually renders      |
| `python -m moe.facts`          | Shows fact coverage and freshness                |
| `python -m moe.tools`          | Shows tool verdicts                              |
| `python -m moe.checker`        | Runs 7 example scenarios in the terminal         |
| `python -m moe.mascot`         | Draws the teacher as text, to check the artwork  |
| `node test_mascot.js`          | Checks the animated teacher actually renders     |

To read the site, open `site\index.html` in your browser.

**If a command errors, send me the output. Don't fix it yourself.** That's my job.

---

## 3b. The scenario checker — the actual product

The homepage opens on a box with three dropdowns:

> **Which level?** Primary 1-3 / Primary 4-6 / Secondary / JC  
> **Who is using it?** For my own work / Students will use it  
> **Which tool?** nine tools, grouped into MOE-built and commercial

You pick three things and get one answer: the verdict, why, what you must do,  
and the ministry quote with a link.

### Why it is three dropdowns and not a chatbox

This was the most important design decision in the project, so it is worth  
being explicit about it.

A free-text "ask me anything" box would feel more modern. It would also be the  
destruction of this site. Our entire claim is that every statement here can be  
checked against a ministry source. A chatbot answers in prose we cannot cite,  
so a teacher pasting it into a risk assessment has nothing to verify. It looks  
authoritative precisely when it should look uncertain.

So the inputs are constrained. Every possible answer was checked in advance  
against the registry, and each one carries its source. When the question falls  
outside the combinations we hold, the checker says **"we cannot answer that"**  
and tells you who to ask instead. That refusal is a feature — same principle as  
the notification layer refusing to send on an unregistered channel.

### The rule that must not be broken

**No rule lives in the JavaScript.** The dropdowns only look up answers that  
Python already produced and vetted. `build_site.py` writes all 72 of them into  
`site/checker-data.js`, and `test_moe.py` compares that file against freshly  
generated data. If someone edits the JavaScript to make a sentence nicer, the  
tests fail rather than the site quietly changing what it says MOE allows.

### One rule worth knowing as the owner

You will see the checker say *"Only with your school's approval"* for any  
commercial tool with students, at every level. That looks stricter than  
expected. It is deliberate and it was a bug we fixed: MOE's wording about  
secondary students says they take greater **ownership** of AI use, which is  
about responsibility, not permission. Reading it as permission would have us  
telling teachers a general chatbot was fine to use.

---

## 3c. The teacher mascot

The homepage has an animated teacher: a small figure rendered in scanline  
dithering, who blinks, sways a pointer, follows your cursor with her eyes, and  
says things in a speech bubble.

**The artwork is ours.** The technique came from a public design; the character  
itself is drawn by our own code (`moe/mascot.py`) from geometry we defined. No  
third-party art, no external assets, nothing downloaded. If you ever publish  
this commercially, there is no licensing question to answer.

### How to change the character

Edit `moe/mascot.py` and rebuild. Useful knobs:

| What                | Where               | Note                                 |
| ------------------- | ------------------- | ------------------------------------ |
| Hair, glasses, body | `build_base()`      | Circles and rects on a 32x32 grid    |
| The pointing arm    | `build_arm()`       | Separate layer, so it can sway       |
| Shading levels      | `INK` dict          | Chosen for how they *dither*         |
| Expression / blink  | `build_base()` eyes | Recorded so a blink can restore them |

Then run `python -m moe.mascot` to see it as text before rebuilding. That is the  
fastest way to tell whether you moved something in the wrong direction.

### The one rule

**All artwork lives in Python, none in JavaScript.** `mascot.js` only decides  
*which* pixels get an ink dash and *when*. It contains no drawing. If you move  
a pixel in the generator, both the animated canvas and the no-JS fallback  
update together — the same rule the fact registry follows, and for the same  
reason: a second copy of anything load-bearing will eventually disagree with  
the first.

### Accessibility and failure behaviour

- **`prefers-reduced-motion`** → a single static frame. No blink, no sway, no  
  typewriter. The speech bubble shows its first line in full.
- **JavaScript disabled** → the static SVG poster shows instead, generated from  
  the same pixel layers. It cannot drift from the animated version.
- **No canvas support** → the renderer returns quietly and the poster stays.
- **DPR capped at 2×** so a high-density phone does not render 4× the pixels  
  for no visible gain.

### Note on the technique, honestly

The dithering is genuine ordered (Bayer 8×8) thresholding, and the scanline  
pitch is what makes shading read as *density of surviving dashes* rather than  
as flat fill. That part is real and it is the whole look.

But be clear-eyed about what it is worth: it is decoration on a compliance  
site, not a feature. Nobody chose this site over another because of the mascot.  
It is worth doing because a friendly character makes a dry subject less  
intimidating to a teacher who is nervous about getting AI rules wrong — and  
because it makes the site memorable. It is not worth an afternoon of anyone's  
time beyond what it has already cost.

---

## 4. The maintenance routine — this is the whole business

This is the part that decides whether the site is worth anything.

### Weekly, about 20 minutes

1. Run `python -m moe.facts`. It tells you how close you are to a stale fact.
2. Check whether MOE has announced anything. Two pages matter:
   - `https://www.moe.gov.sg/news/media-releases` (announcements)
   - `https://www.learning.moe.edu.sg/teachers/teaching-and-learning-on-sls/aied-features/`  
     (new SLS tools)
3. If nothing changed, you are done. Nothing needs rebuilding.

### When a fact goes stale

The build will refuse. That is not a bug — it is the product working. You tell  
me, and I:

1. Re-read the source page
2. Update the quote if MOE changed the wording
3. Update the date
4. Add the new source to the registry if it's a new page
5. Rebuild and re-run the tests

**I never update a date without having read the page.** That's the only thing  
that makes the whole thing honest.

### The one thing that will actually be painful

MOE's SLS features page lists tools with **no version numbers and no dates**. When  
a feature is renamed, widened or quietly retired, the page just changes. If we  
miss it, we will confidently state something false for up to 45 days.

Mitigation: the quarterly check below.

### Quarterly, one afternoon

- Re-read all four sources end to end.
- Look for **new** SLS AI features. MOE adds these; we currently list eight.
- Re-check whether P4 is still the entry point. It has been stable, but it is a  
  policy choice, not a law.
- Check whether a newer parliamentary reply has superseded the May 2026 one.

---

## 5. How we make money, honestly

**Sponsorship from Singapore EdTech vendors.** Slots sit only among commercial  
tool entries.


Three rules are enforced in code, not promises:

1. **Official MOE tools are never for sale.** The build fails if a sponsor is  
   configured next to one. Selling a slot beside something MOE built would  
   destroy the only thing this site has.
2. **Sponsorship does not buy a verdict.** A sponsored tool stays marked, and  
   the mark stays when a verdict drops to a warning. A vendor can correct our  
   facts; they cannot buy a "permitted" rating.
3. **Commercial tools can never be rated "permitted."** We cannot audit a  
   vendor's data handling, so the ceiling is "usable under conditions" and the  
   build fails if anyone tries to exceed it.

**Realistic revenue.** Singapore teachers number roughly 25,000–30,000. A local
EdTech sponsor might plausibly pay **S$500–2,000/month**. One sponsor covers
costs. This is not a large business, and I won't pretend otherwise.

### Why we sell to vendors and never to schools

Two findings from the research drive this, and both are structural rather than
preference.

**MOE guidance discourages engaging schools commercially.** When external
instructors or coaches work with schools, the expectation is that they do not
promote private services to students or parents through that engagement, and do
not leave promotional material in schools. Approaching teachers and schools
directly with a paid product sits badly against that. Sponsorship does not: a
vendor paying for a labelled slot is not using a school relationship to sell
anything.

**Sponsorship is the only channel that does not compromise the ratings.** We
sell attention, never verdicts. If we were selling subscriptions to teachers,
we would eventually be asked to soften a warning for a paying customer, and
that is the whole asset gone.

### The urgency we did not have to invent

MOE has rolled out a **Teacher AI Literacy Professional Learning Roadmap**, with
a first compulsory module due **end of 2026** for all teachers. That gives the
site a dated reason to exist rather than a general one, and it is worth
re-checking the date at each quarterly review — if it moves, this section moves
with it.

**The far bigger prize is Project 1.** This site is a credibility and
distribution asset for the voice business, not a business in itself. It runs
quietly in parallel, as you decided.

---

## 6. Why this is defensible

| Rival approach                   | Why it loses |
| -------------------------------- | ------------ |
| A blog post listing tools        | Goes stale invisibly. No way to check it. |
| A vendor directory selling leads | Every rating is a sponsored rating. Teachers know. |
| A chatbot "ask MOE questions"    | Cannot cite, so cannot be trusted on compliance. |
| A newsletter                    | Answers no question. Nobody subscribes to reading. |
| **This**                         | **Every claim clickable. Build fails when stale. Verdicts enforced by code.** |

The moat is not the writing. It's that a competitor would have to re-verify every  
claim against MOE's sources and accept that their site **breaks** when they don't.  
Nobody does that voluntarily.

---

## 7. What is deliberately missing

Being straight, because pretending otherwise wastes your time:

- **No newsletter signup yet.** A list is worthless at 20 subscribers, and  
  collecting emails from teachers without a reason is how you get reported. Wait  
  for the audience.
- **No paid products yet.** Same reason.
- **No domain, no hosting, no deployment.** The site exists as a local HTML file.
- **No commercial tools beyond one entry.** Listing vendors we haven't verified  
  would undermine the whole premise. We add them only when a vendor gives us  
  verifiable data-retention terms.
- **Tone and coverage notes.** Research, not opinions. This is v1.

---

## 8. The honest risk

**Accuracy is the entire product, and accuracy is not fully in our control.** We  
can guarantee we cited MOE and checked on a date. We cannot guarantee we  
understood MOE correctly, or that MOE hasn't changed something we haven't  
noticed.

That's why the site links every claim to its source. A teacher who disagrees with  
us can check us in ten seconds. That is the safeguard a "trust us, we're  
experts" site cannot offer — and the reason this format can work where a blog  
cannot.

**The failure mode to watch:** a teacher acting on an outdated rule and blaming  
us. The build gate reduces the window. It does not eliminate it. If that ever  
happens, fix the fact, say so publicly, and keep going.

---

## 9. Status

|                        |                                                |
| ---------------------- | ---------------------------------------------- |
| Facts registered       | 22, all with verbatim MOE quotes               |
| Sources                | 4, all official MOE domains                    |
| Tools listed           | 8 official SLS + 1 commercial category         |
| Compliance checks      | 121, all passing                               |
| Build gate             | Working — refuses to publish stale claims      |
| Shortest review window | 22 days                                        |
| Sponsors               | 0                                              |
| Next real deadline     | Re-verify before **8 November 2026** (45 days) |

The shortest window is the binding one. Put **8 November 2026** in your calendar  
as the first re-verification.
