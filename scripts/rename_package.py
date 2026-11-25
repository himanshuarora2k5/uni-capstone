#!/usr/bin/env python3
"""Rename the Python package (default name: leastpriv) everywhere in this repository.

    python scripts/rename_package.py NEWNAME

Renames the package folder, then replaces the old name in text files (.py .md .toml .yml .yaml .json .txt .sh, CODEOWNERS and .gitignore).
The new name must be a valid lower-case Python identifier. Run the tests afterwards. Nothing is committed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

OLD = "leastpriv"
EXTENSIONS = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".txt", ".sh", ".cfg"}
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "build", "dist"}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not re.fullmatch(r"[a-z][a-z0-9_]*", argv[1]) or argv[1] == OLD:
        print(__doc__)
        return 2
    new = argv[1]
    root = Path(__file__).resolve().parent.parent
    pkg_old, pkg_new = root / OLD, root / new
    if not pkg_old.is_dir():
        print(f"no folder {pkg_old}; has it been renamed already?")
        return 2
    if pkg_new.exists():
        print(f"{pkg_new} already exists")
        return 2
    pkg_old.rename(pkg_new)
    changed = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or (path.suffix not in EXTENSIONS and path.name not in ("CODEOWNERS", ".gitignore")):
            continue
        if SKIP_DIRS & set(path.relative_to(root).parts) or path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        updated = re.sub(rf"\b{OLD}\b", new, text)
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed += 1
    print(f"renamed package folder to {new}/ and updated {changed} files. Now run the tests.")
    print("Note: this script keeps the old name in its own docstring on purpose; delete it after renaming if you like.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
