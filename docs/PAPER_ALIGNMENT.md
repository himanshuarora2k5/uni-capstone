# Paper vs repository: what is backed up, what is not

Written on the day v0.1.0 was assembled, against the current draft of the paper. Read this before showing the paper
and the code together. Nothing in the paper was changed because of it.

| Paper statement (section) | Backed by this repo? | Action |
|---|---|---|
| Two prototypes: configuration-driven OCSF log normaliser; hash-chained log with optional anchor (1, 4.2, 4.3) | Yes: `leastpriv/engine/`, `leastpriv/integrity/`, with tests | none |
| "Prototype implemented for BSD syslog and the Apache error-log format; the proxy and CloudTrail formats are specified" (4.2) | The repo implements all four, from files. The paper understates. | Update the sentence when the team is ready |
| E3 detection results (Table 3 and Section 6.2: edits, deletions, swaps, insertions caught; truncation missed without an anchor; rewriting attacker missed without an anchor; all 10 caught with the anchor; position not named for the rewriting attacker) | Yes: `python -m experiments.e3_integrity` reproduces exactly this on a 1,000-record chain (4 of 5, 5 of 5, 0 of 5, 5 of 5; position named 4 of 4, 4 of 4, n/a, 0 of 4). A test pins it. The paper does not say which records fed the chain; the runner uses synthetic syslog-style lines by default and `--source Linux_2k.log` to use real lines. | none, but run it once with the real Linux sample before quoting |
| E3 timing, Table 4 (`[T1]` to `[T5]`, mean and range of five runs on one machine) | The runner exists: `python -m experiments.e3_integrity --timing`. The numbers must come from the machine the paper names. | Run it on the HP Pavilion with Python 3.14.6 and paste the five lines. Do not use numbers from anywhere else |
| E6 pilot, Table 5 (coverage 25%, 50%, 50%, 100%) and the ShopApp-mini description (5.4, 6.3) | Yes: `python -m experiments.e6_pilot` reproduces it; a test pins it. Lookups of the `.example` names are blocked, so nothing leaves the machine. | none |
| E2 log normalisation on the three public Loghub samples: 100% field agreement, 2,000 lines each, all 2,000 Linux lines to the fallback when only Apache is registered, "adding the Apache format took 10 lines of configuration" (5.2, 6.1) | **No.** The repo cannot reproduce it yet: there is no E2 runner and no Loghub data in the repo. The shipped `apache_error.json` is 12 lines, not 10. | Treat the E2 numbers as unverified until the E2 runner (v0.2.0, lane: log engine) is run on the real Loghub files; fix the paper to whatever it prints. Re-count the "10 lines" |
| "The code and the format registry are available at [github link]" (5.1) | True once the repo is pushed and the link is filled in | fill the link |
| "The runs for E2, E3 and the pilot use only the Python standard library ... and contact no third-party servers" (5.1) | E3 and E6 yes. PyYAML is needed only for contract files, which those experiments do not use. | none |
| Sandbox, contract, enforcement, drift detection "specified, not built" (Front note, 4.1, 4.4, 4.5) | Still true for the real components (ECS Fargate sandbox, egress proxy, Access Analyzer, IAM role, enforcer, Prometheus, Grafana, dashboard). v0.1.0 has local stand-ins for the recorder, contract and watcher. | The paper stays true; do not claim more than the roadmap says |

## Things the repo adds that the paper does not mention

- Formats for proxy lines and CloudTrail records use OCSF attribute names beyond the six the paper lists:
  `dst_endpoint.hostname`, `dst_endpoint.port`, `api.service.name`, `api.operation`, `actor.user.uid`, `cloud.region`.
  They have **not** been checked against `schema.ocsf.io`. Reference [15] is part of the paused reference fact-check.
- Apache `severity` keeps the raw level text, not OCSF's severity values.
- CloudTrail `eventName` is not always the IAM action name.

## Still paused

The reference-by-reference fact-check of the 18 references was paused to build this. Partial results (references 1, 3 and 7)
are noted in the working files, not here. Nothing in the paper has been changed from them yet.
