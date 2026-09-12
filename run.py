"""Repository entry point for the shared Q1/Q2 implementation."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    module = Path(__file__).resolve().parent / '解题库' / '第一二问'
    sys.path.insert(0, str(module))
    runpy.run_path(str(module / 'run.py'), run_name='__main__')
