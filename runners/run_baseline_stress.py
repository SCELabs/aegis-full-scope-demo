from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if ROOT.as_posix() not in sys.path:
    sys.path.insert(0, ROOT.as_posix())

from agent.stress_workflow import StressWorkflowRunner


if __name__ == "__main__":
    result = StressWorkflowRunner(use_aegis=False, use_multiagent=False, base_dir=ROOT).run()
    print(json.dumps(result, indent=2))
