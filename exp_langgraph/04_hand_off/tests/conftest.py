from __future__ import annotations

from pathlib import Path
import sys


# Ensure repo modules (api/, agents/, graphs/, etc.) are importable in pytest runs.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

