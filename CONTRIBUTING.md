# Contributing

Six people push to this repository. These rules keep `main` working and let every release build on the last one.

## Workflow

1. `git switch main && git pull`
2. `git switch -c feat/<lane>-<short-name>` (also `fix/...`, `docs/...`)
3. Make a small change (aim for under about 300 lines), with tests.
4. Run everything locally before pushing:
   ```bash
   python -m unittest discover -s tests -t .
   python -m leastpriv demo --workdir demo_check   # then delete the demo_check folder
   ```
5. Push the branch, open a pull request, fill in the template, ask a **different** member to review.
6. Squash-merge when CI is green and there is one approval. Delete the branch.

Commit messages: imperative, one line, say what and why ("Add nginx access-log format"). 

## Releases

- Versions are `vMAJOR.MINOR.PATCH` (`v0.2.0`, ...). Each release is a GitHub milestone (`docs/ROADMAP.md`).
- Every pull request adds one line under `## [Unreleased]` in `CHANGELOG.md`, in **your lane's section**, replacing "(nothing yet)".
- The release manager renames `[Unreleased]` to the version and date, tags `vX.Y.Z` on `main`, and creates the GitHub
  Release with that text. Demos are run from a tag, never from a half-merged branch.

## What "stacking" means in practice

- Stages talk only through the four data shapes in `docs/ARCHITECTURE.md`. Add a producer or consumer; do not reach into
  another stage's internals.
- New log format = one JSON file in `leastpriv/formats/` plus a test. No parser changes.
- Within 0.x: do not change the chain entry shape or hash formula, the contract `version: 1` meaning, CLI command names
  or exit codes, or the Record shape. If a break is unavoidable, put `BREAKING:` in the CHANGELOG line and write a
  migration note in the pull request.
- Old test data must keep passing. If you change behaviour on purpose, change the test in the same pull request and say why.

## Code rules

- Standard library first. `engine/`, `integrity/` and `experiments/` must stay standard-library only (the paper says
  its experiments use only the standard library). A new dependency needs a sentence in the pull request and an entry in
  `requirements.txt` and `pyproject.toml`.
- Tests use `unittest`, live in `tests/`, and must not touch the network or real cloud accounts. Use `samples/`.
- Never commit secrets, AWS keys, real account IDs or real log data. Samples are synthetic.
- Type hints and short docstrings on public functions. Error messages should say what is wrong and which file.
- Text files are LF (`.gitattributes` enforces it); open files with `encoding="utf-8"`.

## Renaming the project

The Python package is called `leastpriv` for now. When the name is decided, one person runs, from the repo root:

```bash
python scripts/rename_package.py NEWNAME     # renames the folder and every mention, then run the tests
```

and commits the result in a single pull request that nobody else is editing around.
