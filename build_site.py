"""Build the AI in SG Schools static site.

    python build_site.py            → audit + build to dist/
    python build_site.py --check    → audit only, write nothing

Exit codes:
    0   clean build (or clean audit in --check mode)
    1   blocking findings — do not publish
    2   build error (unexpected)
"""

from __future__ import annotations

import sys

from moe import builder


def main() -> int:
    check_only = "--check" in sys.argv

    try:
        messages = builder.build(check_only=check_only)
    except RuntimeError as e:
        print()
        print("=" * 70)
        print("BUILD REFUSED")
        print("=" * 70)
        print(f"  {e}")
        print()
        print("  Do not publish. Fix the blocking findings and rebuild.")
        print("=" * 70)
        return 1
    except Exception as e:
        print()
        print("=" * 70)
        print("BUILD ERROR")
        print("=" * 70)
        print(f"  {type(e).__name__}: {e}")
        print("=" * 70)
        return 2

    print()
    print("=" * 70)
    mode = "CHECK" if check_only else "BUILD"
    print(f"AI IN SG SCHOOLS — {mode} COMPLETE")
    print("=" * 70)
    for msg in messages:
        print(f"  {msg}")
    print()
    if not check_only:
        print(f"  Site ready in dist/")
        print(f"  Open dist/index.html in a browser to preview.")
    else:
        print(f"  Check passed. Facts are fresh and tool listings are valid.")
    print()
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
