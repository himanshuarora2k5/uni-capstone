# Roadmap: releases that stack

Each release is a GitHub milestone. A release is done when its issues are merged, CI is green on `main`, the
CHANGELOG has a section for it, and `python -m leastpriv demo` still works. We demo only from tags.
Scope is listed by release, not by date; pick dates as a team (a 1 to 2 week cadence works).

| Release | Theme | What it adds (paper section) | Experiment it unlocks |
|---------|-------|------------------------------|-----------------------|
| **v0.1.0** (this) | Walking skeleton | engine, chain, contract, watcher, stand-in recorder, demo (4.2, 4.3, parts of 4.4 and 4.5) | E3, E6 pilot reproducible |
| v0.2.0 | Evidence and hardening | E2 runner on the three public Loghub samples; OCSF severity and epoch time; check OCSF names against the schema; chain `fsync` option and verify-on-resume; more formats | E2 reproducible |
| v0.3.0 | Real recorder | egress proxy in record mode inside a Docker sandbox; the proxy writes the `egress_proxy` line format, so nothing downstream changes (4.1) | - |
| v0.4.0 | AWS sandbox | run the container as an ECS Fargate task with its own identity; pull CloudTrail events for that identity (4.1) | E1 |
| v0.5.0 | Contract to enforcement | cloud-action part drafted with IAM Access Analyzer; generated IAM role; proxy switched to allowlist mode (4.4) | E4 |
| v0.6.0 | Production watcher | watcher as a service; drift events exported as Prometheus metrics split by type; Grafana alert rules (4.5) | E5 |
| v0.7.0 | Dashboard and provenance | applications, contracts, alerts, searchable history linked to raw source and integrity status; field-level provenance (4.3, 4.5) | - |
| v0.8.0 | AI layer | reviewer summary of a contract and any other part scoped in paper Section 4.6 | - |
| v1.0.0 | Evaluation complete | E1 to E6 run on the AWS deployment, results folded into the paper | all |

Order notes:
- v0.2 can be worked on in parallel with v0.3; v0.4 needs v0.3's proxy; v0.5 needs v0.4's CloudTrail evidence.
- Anything that needs AWS needs a team AWS account and a budget alarm first (an issue for the release manager).
- The paper currently says E1, E4 and E5 are "not run"; keep that sentence true until the release that runs them.
