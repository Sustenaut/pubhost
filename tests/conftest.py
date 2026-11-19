"""pubhost's suite, on pubtest's steps: `Given the program under test is
"pubhost"` runs the pubhost installed beside the Python running this suite
(`make venv`'s), unless PUBHOST_BIN_DIR names another."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("PUBHOST_BIN_DIR", str(Path(sys.executable).parent))
