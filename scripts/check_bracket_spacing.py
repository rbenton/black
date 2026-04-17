#!/usr/bin/env python3
"""Verify the a11y bracket-spacing invariant across all regenerated test fixtures.

For every non-empty `(`, `[`, `{` in a fixture's expected output: the opening
bracket must be followed by exactly one space (unless it's immediately
followed by a newline, i.e. a multi-line split), and its matching close must
be preceded by exactly one space (unless it's at the start of a line, i.e.
also a multi-line split). Empty bracket pairs (`()`, `[]`, `{}`) must be
left untouched.

Not part of pytest — run manually after `regenerate_test_data.py` and before
trusting its output. See VST_A11Y_FORK.md.
"""

import sys
import tokenize
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tests.util import DATA_DIR  # noqa: E402

OPEN = {"(", "[", "{"}
CLOSE = {")", "]", "}"}


# FSTRING_* token types only exist on Python 3.12+ (PEP 701 tokenizer);
# fall back to sentinel values on older runtimes where they're absent.
FSTRING_START = getattr(tokenize, "FSTRING_START", -1)
FSTRING_MIDDLE = getattr(tokenize, "FSTRING_MIDDLE", -2)
FSTRING_END = getattr(tokenize, "FSTRING_END", -3)


def check_source(source: str) -> list[str]:
    errors: list[str] = []
    try:
        tokens = list(tokenize.generate_tokens(StringIO(source).readline))
    except tokenize.TokenError:
        return errors

    # f-string braces are OP tokens too (FSTRING_MIDDLE splits around them) but
    # aren't code brackets subject to the a11y spacing rule.
    skip_types = {
        FSTRING_START,
        FSTRING_MIDDLE,
        FSTRING_END,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.COMMENT,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENCODING,
        tokenize.ENDMARKER,
    }
    fstring_depth = 0
    real_tokens = []
    for t in tokens:
        if t.type == FSTRING_START:
            fstring_depth += 1
        elif t.type == FSTRING_END:
            fstring_depth -= 1
            continue
        if t.type in skip_types:
            continue
        if fstring_depth > 0 and t.string in OPEN | CLOSE:
            continue
        real_tokens.append(t)

    for idx, tok in enumerate(real_tokens):
        if tok.string not in OPEN | CLOSE:
            continue
        if tok.string in OPEN:
            following = real_tokens[idx + 1] if idx + 1 < len(real_tokens) else None
            if following is None:
                continue
            if following.string in CLOSE and following.start[0] == tok.end[0]:
                # empty pair - must be untouched (no space)
                if following.start != tok.end:
                    pair = f"{tok.string}{following.string}"
                    errors.append(
                        f"line {tok.start[0]}: empty pair {pair} has a space"
                    )
                continue
            if following.start[0] != tok.end[0]:
                # multi-line split - opening bracket is last on its line, skip
                continue
            gap = following.start[1] - tok.end[1]
            if gap != 1:
                errors.append(
                    f"line {tok.start[0]}: '{tok.string}' followed by"
                    f" {gap} spaces, expected 1"
                )
        else:
            preceding = real_tokens[idx - 1] if idx > 0 else None
            if preceding is None:
                continue
            if preceding.string in OPEN and preceding.end[0] == tok.start[0]:
                # empty pair, already checked from the open side
                continue
            if preceding.end[0] != tok.start[0]:
                # multi-line split - closing bracket starts its own line, skip
                continue
            gap = tok.start[1] - preceding.end[1]
            if gap != 1:
                errors.append(
                    f"line {tok.start[0]}: '{tok.string}' preceded by"
                    f" {gap} spaces, expected 1"
                )
    return errors


def extract_output_section(text: str) -> str:
    marker = "\n# output\n"
    idx = text.find(marker)
    if idx == -1:
        return text
    return text[idx + len(marker) :]


def main() -> int:
    subdirs = ["cases", "line_ranges_formatted", "miscellaneous"]
    total_errors = 0
    for subdir in subdirs:
        cases_dir = DATA_DIR / subdir
        if not cases_dir.exists():
            continue
        for f in sorted(cases_dir.glob("*.py")):
            text = f.read_text(encoding="utf8")
            output = extract_output_section(text)
            errors = check_source(output)
            if errors:
                total_errors += len(errors)
                print(f"{subdir}/{f.name}:")
                for e in errors:
                    print(f"  {e}")
    if total_errors:
        print(f"\n{total_errors} bracket-spacing violations found")
        return 1
    print("OK: bracket-spacing invariant holds across all fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
