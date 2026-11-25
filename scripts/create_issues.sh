#!/usr/bin/env bash
# Creates labels, milestones and starter issues with the GitHub CLI (gh).
#   gh auth login            # once
#   bash scripts/create_issues.sh [OWNER/REPO]     # run once; running it twice duplicates the issues
# Written without access to a live GitHub account: if a line fails, read the message; these are plain `gh` commands.
set -euo pipefail

REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
echo "Repository: $REPO"

label() { gh label create "$1" -R "$REPO" --color "$2" --description "$3" --force >/dev/null; }
label "area:engine"    1d76db "Log engine and formats"
label "area:integrity" 5319e7 "Hash chain, anchor, verifier"
label "area:recorder"  0e8a16 "Recorder, proxy, CloudTrail"
label "area:contract"  fbca04 "Contract generator and enforcer"
label "area:watcher"   d93f0b "Drift detection and metrics"
label "area:release"   bfdadc "Releases, CI, repository admin"
label "area:docs"      c5def5 "Documentation and the paper"
label "starter"        7057ff "First pull request for a lane"

milestone() { gh api -X POST "repos/$REPO/milestones" -f title="$1" -f description="$2" >/dev/null \
  || echo "  (milestone $1 not created; it may already exist)"; }
milestone "v0.2.0" "Evidence and hardening: E2 runner, OCSF severity/time, chain hardening, more formats"
milestone "v0.3.0" "Real recorder: egress proxy in a Docker sandbox, CloudTrail reader"
milestone "v0.4.0" "AWS sandbox on ECS Fargate (E1)"
milestone "v0.5.0" "Contract to enforcement: Access Analyzer, IAM role, proxy allowlist (E4)"
milestone "v0.6.0" "Production watcher with Prometheus metrics and Grafana alerts (E5)"
milestone "v0.7.0" "Dashboard and field-level provenance"
milestone "v0.8.0" "AI layer (paper Section 4.6)"
milestone "v1.0.0" "All experiments run, results in the paper"

issue() { # title | labels | milestone | body
  gh issue create -R "$REPO" --title "$1" --label "$2" --milestone "$3" --body "$4" >/dev/null
  echo "  created: $1"
}

# ---- starter pull requests (one per lane; new files only, so they do not collide) -------------------
issue "Starter (engine): nginx access-log format" "area:engine,starter" "v0.2.0" \
"Add leastpriv/formats/nginx_access.json (combined log format) and tests in tests/test_formats_nginx.py.
Check every OCSF attribute name you use on schema.ocsf.io and write in the PR which ones you verified.
Done when: tests pass, 'python -m leastpriv formats' lists it, no parser code changed."
issue "Starter (integrity): randomized tamper test" "area:integrity,starter" "v0.2.0" \
"Add tests/test_integrity_random.py: with a fixed seed, edit/delete/swap/insert at random positions of random-length
chains is always detected and the first bad position is reported correctly. No library changes."
issue "Starter (recorder): bigger CloudTrail sample" "area:recorder,starter" "v0.2.0" \
"Add samples/cloudtrail/ with records for sqs, dynamodb and secretsmanager, plus tests that the cloudtrail format maps them
to service:EventName. In the PR, list which CloudTrail event names differ from IAM action names."
issue "Starter (contract): contract diff" "area:contract,starter" "v0.2.0" \
"Add leastpriv/contract/diff.py with diff(a, b) -> added/removed domains and actions, plus tests. CLI wiring comes later."
issue "Starter (watcher): Prometheus text output" "area:watcher,starter" "v0.2.0" \
"Add leastpriv/watcher/metrics.py: render a DriftReport as Prometheus text exposition format, one counter split by type
(domain / cloud_action). Tests only; wiring into the CLI is the next issue."
issue "Starter (release): protect main, tag v0.1.0, release notes" "area:release,starter" "v0.2.0" \
"Follow docs/SETUP_GITHUB.md: push, tag v0.1.0, publish the GitHub Release from CHANGELOG, protect main, add collaborators."

# ---- v0.2.0 ------------------------------------------------------------------------------------------
issue "E2 runner on the three Loghub 2k samples" "area:engine" "v0.2.0" \
"experiments/e2_normalisation.py: field agreement against the ground-truth CSVs for Linux, OpenSSH and Apache; fallback share;
events preserved; the 'only Apache registered' case. Needs the public Loghub files (not committed). Fix the paper to whatever it prints."
issue "Apache level to OCSF severity; add epoch time" "area:engine" "v0.2.0" \
"Map the raw level to OCSF severity values with the registry 'map' option; decide how to get an epoch 'time' (syslog has no year)."
issue "Check OCSF attribute names against schema.ocsf.io" "area:engine" "v0.2.0" \
"Verify dst_endpoint.hostname, dst_endpoint.port, api.service.name, api.operation, actor.user.uid, cloud.region; fix formats and docs."
issue "Chain: fsync option and verify-on-resume" "area:integrity" "v0.2.0" \
"Optional fsync per record (measure cost with E3 timing). Re-opening a log should verify it first, or say why not."
issue "Decide how the anchor is stored outside the log store" "area:integrity" "v0.2.0" \
"One page: second bucket with object lock vs second account vs external timestamping; what each protects against."
issue "Take E3 timing on the HP Pavilion; fill Table 4" "area:docs" "v0.2.0" \
"Run 'python -m experiments.e3_integrity --timing' on the machine named in the paper (Python 3.14.6). Paste into [T1] to [T5]. Also run once with --source Linux_2k.log."
issue "Wire metrics into 'watch' (--metrics-out)" "area:watcher" "v0.2.0" \
"After the starter metrics module lands: leastpriv watch --metrics-out FILE."
issue "contract diff command and deterministic review summary" "area:contract" "v0.2.0" \
"Expose diff as 'contract diff A B'; add a plain-text deterministic summary to 'contract show'."

# ---- v0.3.0 ------------------------------------------------------------------------------------------
issue "Design: egress proxy in record mode" "area:recorder" "v0.3.0" \
"One page: tool choice, how it records (host and port), the exact egress_proxy line it must write, how it runs in a Docker sandbox."
issue "CloudTrail reader by identity and time window" "area:recorder" "v0.3.0" \
"Produce raw CloudTrail records for the sandbox identity; same cloudtrail format downstream. Note CloudTrail delivery delay."

# ---- release admin -----------------------------------------------------------------------------------
issue "AWS account for the team and a budget alarm" "area:release" "v0.4.0" \
"Needed before any AWS work. Agree who pays/owns it, set a budget alarm, never commit keys."

echo "Done. Assign yourselves on GitHub; the label area:* shows the suggested lane (docs/TASKS.md)."
