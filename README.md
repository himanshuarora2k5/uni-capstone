# [title]

> Working package name: `leastpriv` (the project name is still open; see "Renaming the project" in `CONTRIBUTING.md`).

A deployment-pipeline step that runs a newly built application in a sandbox with test traffic, records the
outbound domains and cloud actions it uses, and turns that record into a **reviewable least-privilege
contract**. In production a watcher flags anything outside the approved contract. Every observation goes
through one log engine that maps events to OCSF-shaped records and stores them in a **hash-chained,
tamper-evident log**.

This repository is built so that each release **adds to** the previous one: the pieces below are real
stages of the full system, not a throw-away demo. See `docs/ARCHITECTURE.md` and `docs/ROADMAP.md`.

## Status: v0.1.0 "walking skeleton"

Everything below runs locally on files, with no cloud account.

| Stage (paper section)              | In v0.1.0                                                                                   | Not yet (release)            |
|------------------------------------|---------------------------------------------------------------------------------------------|------------------------------|
| Log engine (4.2)                   | JSON format registry, parser with fallback, 4 formats: BSD syslog, Apache error, egress-proxy line, CloudTrail record | more formats, OCSF severity/time normalisation (v0.2) |
| Integrity (4.3)                    | hash chain, anchor, verifier that names the first bad entry                                  | history-tree option, field-level provenance (v0.7) |
| Sandbox and recorder (4.1)         | in-process stand-in recorder (Python audit hook) writing the same line format the proxy will | real egress proxy + sandbox (v0.3), AWS ECS Fargate + CloudTrail (v0.4) |
| Contract generator (4.4)           | draft YAML contract from a verified log, reviewer approval step                              | IAM role via Access Analyzer + enforcement (v0.5) |
| Drift detection (4.5)              | alert-only watcher; refuses a log that fails verification                                    | Prometheus metrics, Grafana alerts (v0.6), dashboard (v0.7) |
| AI layer (4.6)                     | -                                                                                            | v0.8                          |

## Quick start

Needs Python 3.10 or newer and one package (`PyYAML`, used only for contract files). The log engine,
integrity layer and experiments use the standard library only.

```bash
git clone <repo-url> && cd <repo-folder>
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

python -m unittest discover -s tests -t .      # all tests
python -m leastpriv demo                       # whole pipeline on the sample app (about 1 second)
```

Developed and tested on Python 3.13; CI runs 3.10, 3.12 and 3.13 on Linux. Python 3.14 has not been tried yet.

## Commands

```text
python -m leastpriv formats                                   list registered log formats
python -m leastpriv ingest FILE... --log run.jsonl --anchor-out ../anchors/run.anchor
python -m leastpriv verify --log run.jsonl --anchor-file ../anchors/run.anchor
python -m leastpriv contract generate --log run.jsonl --app NAME -o contract.yaml
python -m leastpriv contract show contract.yaml
python -m leastpriv contract approve contract.yaml --by "Reviewer Name"
python -m leastpriv watch --contract contract.yaml --log prod.jsonl [--drift-out drift.jsonl]
python -m leastpriv demo [--workdir DIR]
```

Exit codes: `0` fine, `1` a finding (verification failed / drift found), `2` could not run (bad input, or the log
did not verify when `watch` / `contract generate` needed it to). A walkthrough with the files in `samples/` is in
`docs/DEMO.md`.

Experiments (each prints a table; `--json` for raw numbers):

```text
python -m experiments.e3_integrity [--timing] [--source Linux_2k.log]   tamper detection (+ timing)
python -m experiments.e6_pilot                                            coverage pilot on ShopApp-mini
```

## Layout

```text
leastpriv/            the package: engine/ integrity/ recorder/ contract/ watcher/ demo/ + cli.py pipeline.py observe.py
leastpriv/formats/    one JSON file per log format (add a file = support a new format)
experiments/          runners that reproduce the paper's experiments
samples/              tiny synthetic inputs (not real telemetry)
tests/                unittest suite
docs/                 ARCHITECTURE, ROADMAP, TASKS, DEMO, SETUP_GITHUB, PAPER_ALIGNMENT (CONTRIBUTING.md is in the root)
```

## Honest limits of v0.1.0

- The recorder is a stand-in: it sees only DNS lookups made by Python code in the same process. It is not the
  egress proxy and it does not see cloud actions; the demo's CloudTrail records are written by the demo script.
- CloudTrail event names are not always identical to IAM action names (the full system uses IAM Access Analyzer for
  that step); v0.1 builds the action as `service:EventName`.
- The OCSF attribute names used for the proxy and CloudTrail formats have not been checked against the schema yet
  (tracked in `docs/PAPER_ALIGNMENT.md`).
- A hash chain alone cannot detect truncation or a full rewrite; that needs the anchor stored outside the log store.
- The watcher only alerts; it does not block.
