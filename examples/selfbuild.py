"""Use the process supervisor to build and test VL-K itself."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from process import Supervisor
with Supervisor() as s:
    h = s.spawn(['make', 'test'], cwd=ROOT, env=dict(os.environ))
    status = s.wait(h)
    s.release(h)
sys.exit(status if status >= 0 else 128-status)
