#!/usr/bin/env python3
"""medpaper workflow driver.

    .venv/Scripts/python.exe tools/wf.py status

Stdlib only, so the gate engine keeps working even when the science
virtualenv is missing or broken.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ required (tomllib). Found %s" % sys.version.split()[0])

from wfcore.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
