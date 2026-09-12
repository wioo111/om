"""Rebuild the repository paper from the shared editable manuscript."""
from pathlib import Path
import subprocess
import sys

if __name__=='__main__':
    subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'第一二问/run.py'),'paper'],check=True)
