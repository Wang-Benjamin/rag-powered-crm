from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CRM_ROOT = ROOT / "prelude" / "prelude-crm"
SHARED_ROOT = ROOT / "prelude" / "prelude-shared"

for entry in (CRM_ROOT, SHARED_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
