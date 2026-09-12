"""Thin Q1 adapter; all geometry resides in 第一二问/src/q12."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    module = Path(__file__).resolve().parents[1] / '第一二问'
    sys.path.insert(0, str(module))
    sys.argv.insert(1, 'q1')
    runpy.run_path(str(module / 'run.py'), run_name='__main__')
