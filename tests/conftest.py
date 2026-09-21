from __future__ import annotations

import sys
from pathlib import Path

COURSE_DIR = (
    Path(__file__).parents[1]
    / "curriculum"
    / "advanced"
    / "01-production-ai-development"
)
sys.path.insert(0, str(COURSE_DIR))
