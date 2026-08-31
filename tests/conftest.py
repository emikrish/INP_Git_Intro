"""Make the repository's scripts importable from the tests.

``code/`` and ``.github/scripts/`` are not packages, so the paths are added
explicitly rather than relying on installation.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

for scripts_dir in (REPO_ROOT / "code", REPO_ROOT / ".github" / "scripts"):
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
