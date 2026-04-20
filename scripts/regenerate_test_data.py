#!/usr/bin/env python3
"""Regenerate expected output sections in test data files after a formatting change."""

import sys
from pathlib import Path

# Make sure we use the local black
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import black  # noqa: E402
from tests.util import DATA_DIR, parse_mode  # noqa: E402

EMPTY_LINE = "# EMPTY LINE WITH WHITESPACE" + " (this comment will be removed)"


def regenerate_file(file_path: Path) -> bool:
    """Regenerate the output section of a test data file. Returns True if changed."""
    with open(file_path, encoding="utf8") as f:
        original = f.read()
        raw_lines = original.splitlines(keepends=True)

    # Parse flags and find structure
    flags_line: str | None = None
    args = parse_mode("")  # default (empty flags)
    input_lines: list[str] = []
    has_output_marker = False
    flags_in_input = False  # True when flags line is included in the input section

    result = input_lines
    for line in raw_lines:
        if not input_lines and line.startswith("# flags: "):
            flags_line = line
            args = parse_mode(line[len("# flags: "):])
            if args.lines:
                # line-ranges tests: the flags line is retained in the input section
                flags_in_input = True
                result.append(line)
            continue
        if line.rstrip() == "# output":
            has_output_marker = True
            break
        result.append(line)

    mode = args.mode
    lines_param = args.lines  # may be empty

    # Get the input source (strip EMPTY_LINE markers as read_data_from_file does)
    raw_input = "".join(input_lines)
    source = raw_input.replace(EMPTY_LINE, "").strip() + "\n"

    # Format with current black
    try:
        new_output = black.format_str(source, mode=mode, lines=lines_param)
    except Exception as e:
        print(f"  SKIP (format error): {file_path.name}: {e}")
        return False

    # The flags header line goes at the top unless it was already in the input section
    header = "" if flags_in_input else (flags_line or "")

    if has_output_marker:
        # Reconstruct: header + input + "# output\n" + new_output
        new_content = header + raw_input + "# output\n" + new_output
    else:
        # No output marker: the file IS the canonical format. Update to new format.
        new_content = header + new_output

    if new_content == original:
        return False

    with open(file_path, "w", encoding="utf8") as f:
        f.write(new_content)
    return True


def main() -> None:
    subdirs = ["cases", "line_ranges_formatted", "miscellaneous"]
    # These files are intentionally malformatted inputs used in diff tests;
    # they must not be reformatted.
    # decorators.py abuses the "# output" marker to separate old vs. relaxed
    # decorator syntax (not input/expected-output); reformatting it corrupts
    # that structure. See test_get_features_used_decorator in test_black.py.
    # force_py36.py's expected output depends on --target-version py36 (passed
    # directly by test_black.py, not encoded in a "# flags:" line), which this
    # script formats without; regenerating it drops the py36-only trailing
    # comma after *rest.
    skip_files = {"blackd_diff.py", "decorators.py", "force_py36.py"}
    total_changed = 0
    total_errors = 0
    total_files = 0
    for subdir in subdirs:
        cases_dir = DATA_DIR / subdir
        if not cases_dir.exists():
            continue
        files = sorted(cases_dir.glob("*.py"))
        total_files += len(files)
        for f in files:
            if f.name in skip_files:
                continue
            try:
                if regenerate_file(f):
                    print(f"  updated: {subdir}/{f.name}")
                    total_changed += 1
            except Exception as e:
                print(f"  ERROR: {subdir}/{f.name}: {e}")
                total_errors += 1
    unchanged = total_files - total_changed - total_errors
    print(
        f"\n{total_changed} files updated, {total_errors} errors, {unchanged} unchanged"
    )


if __name__ == "__main__":
    main()
