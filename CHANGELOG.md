# Changelog

Format: [Keep a Changelog](https://keepachangelog.com). Versions follow `docs/ROADMAP.md`.
Every pull request adds one line under **Unreleased**, in its own lane's section, replacing "(nothing yet)".
(Separate sections mean six people editing at once do not collide.)

## [Unreleased]

### engine

- (nothing yet)

### integrity

- (nothing yet)

### recorder

- (nothing yet)

### contract

- (nothing yet)

### watcher

- (nothing yet)

### release and docs

- (nothing yet)

## [0.1.0] - walking skeleton

### Added
- Log engine: JSON format registry (one file per format, regex or JSON), normaliser with fallback that never drops an
  event and always keeps the raw text; formats `syslog_bsd`, `apache_error`, `egress_proxy`, `cloudtrail`.
- Integrity: append-only hash-chained log (`SHA-256(prev || canonical JSON)`), anchor file support, verifier that
  names the first bad entry; documented limits (truncation and full rewrite need the anchor).
- Contract: draft generator from a verified log, YAML file with `draft` / `approved` status and reviewer name, pattern
  matching with `*`, rejection of match-everything patterns.
- Watcher: alert-only drift detection for destinations and cloud actions; refuses a log that fails verification.
- Recorder: in-process stand-in (Python audit hook on DNS lookups) that writes the `egress_proxy` line format.
- CLI: `formats`, `ingest`, `verify`, `contract generate|approve|show`, `watch`, `demo`.
- ShopApp-mini sample application and three traffic sources.
- Experiments: `e3_integrity` (tamper detection and timing) and `e6_pilot` (coverage), with tests that pin the
  behaviour described in the paper.
- Docs, CI, issue/PR templates, team task split.
