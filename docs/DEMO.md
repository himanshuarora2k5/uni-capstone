# Demo script (about 5 minutes)

Run from a clean checkout of tag `v0.1.0`, venv active.

## 0. Say what it is (30 seconds)

"This is version 0.1 of the system in our paper. It is a working slice of the pipeline: record what an application
does, turn that into a contract a person approves, then watch for anything outside the contract, with the evidence
kept in a log that shows tampering. The sandbox on AWS is not built yet; here a stand-in recorder plays that role.
The code is built so each later release adds a stage and does not replace the earlier ones."

## 1. Tests (20 seconds)

```bash
python -m unittest discover -s tests -t .
```
Expect `OK` at the end.

## 2. The whole pipeline on the sample app (2 minutes)

```bash
python -m leastpriv demo
```
Walk through the five numbered steps as they print:

1. **Sandbox run**: the sample shop app gets test traffic; the recorder sees 2 outbound destinations (images, payments).
2. **Log engine**: lines are normalised into OCSF-shaped events and stored in a hash-chained log.
3. **Contract**: drafted from the log; note that the analytics and notifications destinations are **not** in it, because no
   test reached those two routes. A person approves it.
4. **Production**: real-user traffic reaches those two routes plus one extra cloud action (`s3:PutObject`); the watcher
   reports 3 drift events. (This is the "coverage depends on test traffic" problem from the paper, shown live.)
5. **Tampering**: an attacker renames the analytics destination in the log to hide it, and the verifier names the exact
   entry. Cutting entries off the end is **not** caught by the chain alone but **is** caught with the anchor.

Then show one file: `python -m leastpriv contract show <workdir>/contract.yaml` (the demo prints the folder).

## 3. The two experiments from the paper (1 minute)

```bash
python -m experiments.e3_integrity
python -m experiments.e6_pilot
```
The first prints the tamper-detection table (4 of 5, 5 of 5, 0 of 5, 5 of 5); the second prints coverage 25%, 50%, 50%, 100%.

## 4. Manual walkthrough with the sample files (if asked "can I see the steps?")

```bash
python -m leastpriv ingest samples/shopapp/sandbox_proxy.log samples/shopapp/sandbox_cloudtrail.json --log sbx.chain.jsonl --anchor-out sbx.anchor
python -m leastpriv verify --log sbx.chain.jsonl --anchor-file sbx.anchor
python -m leastpriv contract generate --log sbx.chain.jsonl --app shopapp-mini -o contract.yaml
python -m leastpriv contract approve contract.yaml --by "Your Name"
python -m leastpriv ingest samples/shopapp/prod_proxy.log samples/shopapp/prod_cloudtrail.json --log prod.chain.jsonl
python -m leastpriv watch --contract contract.yaml --log prod.chain.jsonl
```
Delete the files this creates afterwards (`sbx.*`, `prod.*`, `contract.yaml`); `.gitignore` already hides the chain files.

## 5. What to say about what is NOT done (be upfront; it lands better)

- No AWS yet: no ECS Fargate sandbox, no real CloudTrail, no IAM role generation, no enforcement. (Releases v0.3 to v0.5.)
- The recorder here only sees lookups made inside one Python process.
- The watcher alerts; it does not block. No dashboard or Prometheus yet. (v0.6, v0.7.)
- The log-normalisation experiment on the public Loghub samples (E2) is not wired into the repo yet. (v0.2.)

## Likely questions

- **Why a hash chain?** Each entry's hash covers the previous hash, so changing any entry breaks everything after it.
  It cannot see truncation or a full rewrite on its own, which is why the anchor lives outside the log store.
- **Is the contract trustworthy?** It is a draft from observed behaviour; a person approves it. Anything the tests
  never triggered is missing, and that is exactly what the watcher is for.
- **How do we add a new log format?** Drop a JSON file into `leastpriv/formats/`; no code change.
- **What is each person doing next?** `docs/TASKS.md` and `docs/ROADMAP.md`.
