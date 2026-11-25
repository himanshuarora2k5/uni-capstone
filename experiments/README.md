# Experiments

Runners that reproduce what the paper reports. Run from the repository root.

| Paper | Command | Needs | Status |
|-------|---------|-------|--------|
| E3 tamper detection (Table 3) | `python -m experiments.e3_integrity` | nothing | reproduces the paper's pattern; pinned by `tests/test_experiments.py` |
| E3 timing (Table 4) | `python -m experiments.e3_integrity --timing` | nothing; **run on the machine the paper names** | runner ready; numbers not yet taken on the team laptop |
| E6 coverage pilot (Table 5) | `python -m experiments.e6_pilot` | nothing | reproduces 25 / 50 / 50 / 100 percent |
| E2 log normalisation | not written yet | the three Loghub 2k samples and their ground-truth CSVs (public, from github.com/logpai/loghub) | v0.2.0, lane: log engine |
| E1, E4, E5 | not written | the AWS deployment | v0.4.0 to v0.6.0 |

Use `--json` for raw numbers. `--source FILE` makes E3 use the first N lines of a real log (for example the Linux sample)
instead of synthetic syslog-style lines.

All three runners use only the standard library and never contact a third-party server (E6 blocks the `.example`
lookups it records).
