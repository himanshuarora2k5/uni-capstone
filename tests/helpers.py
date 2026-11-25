from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SAMPLES = REPO / "samples"
SHOP = SAMPLES / "shopapp"


class TmpCase(unittest.TestCase):
    """Test case with a fresh temporary folder in self.tmp."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="leastpriv-test-")
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)

    def write(self, name: str, text: str) -> Path:
        p = self.tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def write_json(self, name: str, obj) -> Path:
        return self.write(name, json.dumps(obj))


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
