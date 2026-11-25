# Who works on what

This is a **suggested** split of the six of you into six lanes that mostly touch different files, so pull requests
rarely collide. Swap lanes however you like; keep one named owner per lane so every area has a person who knows it.

| Lane | Suggested owner | Owns (folders / files) | First pull request (small, new files only) |
|------|-----------------|------------------------|--------------------------------------------|
| Release manager and integration | Himanshu Arora | `cli.py`, `pipeline.py`, `docs/`, `.github/`, `CHANGELOG.md`, tags | Push v0.1.0, protect `main`, create issues (`docs/SETUP_GITHUB.md`) |
| Log engine and formats | Pranav Sudhir | `leastpriv/engine/`, `leastpriv/formats/`, E2 runner | New format file `nginx_access.json` + tests (check each OCSF attribute name on schema.ocsf.io and write down which ones you verified) |
| Integrity | Sanyam Bedi | `leastpriv/integrity/`, `experiments/e3_integrity.py` | `tests/test_integrity_random.py`: random tampering at random positions is always detected (fixed seed) |
| Recorder | Rhythm Sharma | `leastpriv/recorder/`, `samples/` | Bigger CloudTrail sample (sqs, dynamodb, secretsmanager) + format tests; list what is missing for real IAM actions |
| Contract and enforcer | Gurpreet Singh | `leastpriv/contract/` | `leastpriv/contract/diff.py`: compare two contracts (added/removed domains and actions) + tests |
| Watcher and metrics | Vansham | `leastpriv/watcher/`, later the dashboard | `leastpriv/watcher/metrics.py`: render a `DriftReport` as Prometheus text format + tests |

Names are taken from the paper's author list; the order is not a ranking.

## First hour for everyone

1. Clone the repo, follow the Quick start in `README.md`: tests pass, `python -m leastpriv demo` runs.
2. Read `docs/ARCHITECTURE.md` (10 minutes). It is short on purpose.
3. Create a branch `feat/<lane>-<short-name>`, do your first pull request from the table above, ask a **different**
   member to review it, squash-merge when CI is green.
4. Add one line in **your lane's section** under `## [Unreleased]` in `CHANGELOG.md` (replace "(nothing yet)") in the same pull request.

## Rules that stop us breaking each other

- Do not push to `main`. Everything goes through a pull request with one approval from another member.
- Stay in your lane's folders. Need a change somewhere else? Open an issue or ask the owner; small fixes are fine if
  the owner reviews them.
- `cli.py`, `pipeline.py`, `README.md` and `CHANGELOG.md` are shared. Keep edits there short and rebase often.
- Never change the four shared data shapes in `docs/ARCHITECTURE.md` without telling everyone first.
- Every pull request needs tests. No test, no merge.

## Where the next releases need hands (v0.2.0)

Himanshu picks the order; each item is also an issue if you run `scripts/create_issues.sh`.

- **Pranav**: E2 runner on the three public Loghub samples (Linux, OpenSSH, Apache) with the ground-truth CSVs;
  OCSF `severity` mapping and epoch `time`.
- **Sanyam**: chain `fsync` option; verify-on-resume; a `leastpriv anchor` helper (print/compare); decide how the
  anchor is stored outside the log store (second S3 bucket with object lock, or a second account).
- **Rhythm**: design the egress proxy for v0.3 (one page: tool choice, record mode, line format it must write);
  CloudTrail reader that fetches by identity and time window.
- **Gurpreet**: `contract diff` command; contract review summary (plain text, deterministic); pattern rules for
  domains (what `*` may and may not match).
- **Vansham**: wire `metrics.py` into a `leastpriv watch --metrics-out FILE` option; Grafana alert rule draft.
- **Himanshu**: LICENSE decision, branch protection, release notes for v0.1.0, AWS account and budget alarm.
