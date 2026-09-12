"""v3 一站式验证：跑核心库自检 + 算例与可视化 + 生成 PDF.

v3.5.6.1 修复：设 OPENBLAS_NUM_THREADS=1 避免 OpenBLAS 多线程内存错。
环境变量：OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1, MKL_NUM_THREADS=1, PYTHONIOENCODING=utf-8.
最新日志：logs/verify_v3.5.6.1.log"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()


def run(label: str, cmd: list) -> None:
    print(f"\n>>> [{label}] {' '.join(cmd)}")
    env = {**os.environ,
           "OPENBLAS_NUM_THREADS": "1",
           "OMP_NUM_THREADS": "1",
           "MKL_NUM_THREADS": "1",
           "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run(cmd, cwd=str(HERE), env=env)
    if r.returncode != 0:
        print(f"[FAIL] {label} returncode={r.returncode}")
        sys.exit(r.returncode)


def main() -> None:
    py = sys.executable
    run("核心库自检",     [py, str(HERE / "problem1_core_v3.py")])
    run("图重画(v3.5.6)", [py, str(HERE / "regen_figures.py")])
    run("PDF 生成",       [py, str(HERE / "gen_problem1_pdf_v3.py")])
    print("\n[OK] v3 全部完成")
    print(f"产物：{HERE}\\问题一建模_v3.pdf")


if __name__ == "__main__":
    main()
