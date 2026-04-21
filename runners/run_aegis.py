from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if ROOT.as_posix() not in sys.path:
    sys.path.insert(0, ROOT.as_posix())

from agent.workflow import WorkflowRunner


if __name__ == "__main__":
    result = WorkflowRunner(use_aegis=True, base_dir=Path(__file__).resolve().parents[1]).run()
    print(json.dumps(result, indent=2))
