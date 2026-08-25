# Accessibility fork — maintenance model

## Why this fork exists

This is a fork of [psf/black](https://github.com/psf/black) with one added feature: a
single space inside every non-empty bracket pair (`foo(1, 2)` → `foo( 1, 2 )`), to make
bracketed code easier for screen readers to parse aloud. That's the entire scope of the
fork. Everything else should track upstream as closely as possible.

## Branch model

- `master` — mirrors upstream `psf/black` (remotes: `psf`, `upstream`, both point at
  `psf/black`; `origin` is `rbenton/black`).
- `a11y` — the feature branch. Branched from `master` at a release tag (currently
  `26.5.1`, originally `26.3.1`). Carries a small, fixed number of commits on top of
  that tag — currently 4:
  1. `5d11fd2f` — the bracket-spacing feature itself (logic + regenerated fixtures +
     `scripts/regenerate_test_data.py` + `scripts/check_bracket_spacing.py`).
  2. `2abf297b` — pre-commit flake8/mypy fixups.
  3. `00dd8f11` — editable-install schema entrypoint test fix.
  4. `71aad679` — fix `Line.__str__` mutating a shared leaf's prefix during split
     arbitration (discarded candidate splits were corrupting the accepted split's
     bracket spacing — see "Where the feature actually lives" below). Bug fixes to the
     feature itself get their own commit appended here rather than being folded into
     `5d11fd2f` — keep this list in sync when that happens.
- `a11y` is a **stable, reused branch name** — not renamed per release. It gets rebased
  onto each new upstream tag, not merged, and not re-created via cherry-pick onto a
  fresh branch each time.

## Where the feature actually lives

Two functions are the source of truth. After every rebase, re-read these first —
upstream refactors can silently route bracket handling around them without any test
failing:

- `whitespace()` in `src/black/nodes.py` — decides `SPACE` vs `NO` before/ after bracket
  tokens. This is where "space after opening bracket, space before closing bracket,
  unless empty" is encoded.
- `Line.__str__()` in `src/black/lines.py` — strips the stray leading space when a
  line's first leaf is a closing bracket (the split-line case, e.g. a multi-line call
  where the closing `)` sits alone on its own line).
- `src/black/linegen.py` — line-splitting logic. Not part of the a11y change itself, but
  it's the other place bracket placement decisions get made when black breaks a long
  call/collection across lines. Worth scanning for new splitting paths that might bypass
  the two functions above.

**Versioning:** the fork pins a static `version` in `pyproject.toml` (mirrored in
`src/_black_version.py`) instead of deriving it from git tags via `hatch-vcs`.
Installers like `uv`/`pip` fetch this repo via a shallow clone of the pinned commit SHA,
which drops tags — `hatch-vcs`'s git-describe then falls back to a bogus ancient version
(observed: `19.10b1.dev...`), which trips Dependabot vulnerability alerts against the
real `black` PyPI package's old-version advisories. A static version sidesteps that
entirely — it must always equal the upstream tag `a11y` is currently rebased onto (no
fork-specific suffix), so a package manager/Dependabot sees exactly the upstream
version's fix status. Update it every sync — see step 3 below.

**`scripts/regenerate_test_data.py` skip list — files it must never touch:**

- `blackd_diff.py` — intentionally malformatted diff-test input.
- `decorators.py` — abuses the `# output` marker to separate old vs. relaxed decorator
  syntax (not input/expected-output); reformatting it corrupts that structure and
  duplicates the file's content. Only used for feature-detection parsing
  (`test_get_features_used_decorator`), never for format comparison.
- `force_py36.py` — its expected output depends on `--target-version py36`, passed
  directly by `test_black.py` rather than encoded in a `# flags:` line. Regenerating it
  with the script's default (no target version) mode drops the py36-only trailing comma
  after `*rest`.

If a sync run reports these files as "updated" by the script, that's the bug reappearing
— revert the file and confirm it's still in `skip_files`.

## Sync workflow (pulling a new psf/black release)

1. Fetch upstream tags: `git fetch upstream --tags`.
2. Rebase the feature branch onto the new tag:
   ```
   git rebase --onto <new-tag> <old-tag> a11y
   ```
   Resolve any conflicts commit-by-commit (there are only 3 commits, so this is small).
   Conflicts will show up exactly where upstream also touched bracket-related code or
   the same test fixtures — that's the signal to read closely, not just resolve
   mechanically.
3. Set the static version to exactly the new upstream tag (no fork-specific suffix):
   update `version = "..."` in `pyproject.toml` (`[project]`) and the matching
   `version = "..."` in `src/_black_version.py`. Keep them identical to each other and
   to the tag. This is what consumers pinning this fork by commit SHA actually see in
   their lockfiles — a stale version here means a package manager (and Dependabot) will
   keep seeing the old number.
4. Regenerate fixtures: run `python scripts/regenerate_test_data.py`. This bulk-rewrites
   the `# output` sections of `tests/data/**` to match whatever the rebased code now
   produces.
5. **Run the bracket-invariant check before trusting step 4's output.**
   `regenerate_test_data.py` blindly accepts the new output as correct — if the
   whitespace logic broke, it will happily bake the wrong spacing into fixtures and the
   suite will still pass. Guard against this with
   `PYTHONPATH=. python scripts/check_bracket_spacing.py`, which tokenizes every
   regenerated case file and asserts: every non-empty `(`, `[`, `{` is followed by
   exactly one space, every matching close is preceded by exactly one space, and empty
   bracket pairs (`()`, `[]`, `{}`) are untouched (multi-line splits and f-string `{}`
   are excluded). It is expected to print a nonzero count of violations.

   **Why violations are expected, as a rule (not a fixed file list):** any fixture whose
   expected output contains a `# fmt: off`/`# fmt: skip` region, or any `line_ranges_*`
   fixture (partial-range formatting also preserves the untouched part verbatim),
   necessarily preserves original (pre-fork) spacing in that region — that's the whole
   point of those directives, and it applies to the entire `fmtonoff*.py`/`fmtskip*.py`/
   `line_ranges_*.py` family, not just a few named examples. Also expected: files in
   `regenerate_test_data.py`'s `skip_files` list plus `blackd_diff.py` (never
   reformatted — intentionally malformatted/skip-marked inputs), `python2_detection.py`
   (never reformatted — `SKIP (format error)`, invalid syntax pre-3.x), and
   `debug_visitor.py` (violations are in docstring text, not real brackets). Do not try
   to keep this doc's file list exhaustive — it will drift. Treat "which files are
   expected to violate" as a _category test_ (does the violation sit in an
   fmt-off/fmt-skip/line-ranges/never-reformatted region?), not a lookup against names
   written down here.

   **The check that matters — diff against a committed baseline, not memory or this
   doc's examples:**

   ```
   PYTHONPATH=. python scripts/check_bracket_spacing.py > /tmp/bracket_check.txt 2>/dev/null
   diff tests/data/bracket_spacing_baseline.txt /tmp/bracket_check.txt
   ```

   - Lines that _disappear_ from the baseline are fine (a fixture got fixed/simplified
     upstream) — just re-save the baseline (see below).
   - Lines that are _new_ on a file that actually changed in this sync are the real
     signal — investigate before regenerating the baseline.
   - Once you've confirmed the diff is clean (only expected/explained changes),
     regenerate the baseline so the next sync starts from an accurate snapshot:
     `PYTHONPATH=. python scripts/check_bracket_spacing.py > tests/data/bracket_spacing_baseline.txt 2>/dev/null`
     and commit it alongside the fixture changes.

6. Run the full test suite (`pytest`) plus pre-commit (`flake8`, `mypy`). **After
   running pytest, run `git status`.** A few tests (currently `test_python315`,
   `test_python37` in `tests/test_black.py`) call `invokeBlack([str(source_path), ...])`
   directly on a real fixture path under `tests/data/`, which reformats that file on
   disk as a side effect — including the pre-`# output` "source" section, which is
   supposed to stay in its original (unformatted) syntax. With vanilla black this is a
   no-op; with the a11y feature it bracket-spaces the source section too, silently
   mutating a tracked fixture (`tests/data/cases/python315.py` as of the 26.5.1 sync).
   `git checkout --` any such file before committing — do not commit the mutation.
7. Done when: full suite passes, invariant-check script passes clean, the version bump
   from step 3 is in place in both files, and any _new or changed_ upstream test fixture
   touching brackets has been visually confirmed to have the expected single-space
   padding.
8. Push the rebased branch: `git push --force-with-lease origin a11y` (force-push is
   expected here — rebase rewrites history on a feature-only branch).

## Known edge-case rules encoded in the feature (from the original commit)

- Empty brackets (`foo()`, `[]`, `{}`) are never padded.
- Multi-line bracket splits get no leading/trailing space on the lines that just hold
  the opening/closing bracket — only single-line bracket content gets the space
  treatment.
- Applies uniformly to calls, collections, slices, type annotations, and decorators.
