from __future__ import annotations

"""
QA-004 automated regression runner.

Runs the core render-compatibility tests:
- output type normalization behavior
- GeoParquet -> GeoJSON conversion source mapping
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = [
    ROOT / "tests" / "test_output_type_normalization.py",
    ROOT / "tests" / "test_geoparquet_conversion_render_source.py",
]


def main() -> int:
    for test in TESTS:
        print(f"== Running {test.name} ==")
        result = subprocess.run([sys.executable, str(test)], cwd=str(ROOT))
        if result.returncode != 0:
            print(f"FAIL: {test.name}")
            return result.returncode
    print("PASS: Render compatibility regression suite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
