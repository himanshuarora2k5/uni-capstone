"""Least-privilege contracts from sandboxed runs, with a tamper-evident OCSF-mapped log.

Package layout (one folder per pipeline stage, see docs/ARCHITECTURE.md):

    engine      log engine: format registry + normaliser (OCSF-shaped events)
    integrity   hash-chained log, anchor, verifier
    recorder    sources of raw events (v0.1: in-process stand-in for the egress proxy)
    contract    contract generator, contract file (YAML) reader/writer
    watcher     drift detection: compares events with an approved contract
"""

__version__ = "0.1.0"
