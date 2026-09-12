"""问题2 v3 一站式验证脚本.

顺序执行：
  1) 核心库 7/7 自检
  2) 5 张图算例 + problem2_v3_results.json
  3) PDF 生成（中文 + Unicode 数学符号）
  4) 备份 PDF
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()
PY = sys.executable


def run(label: str, args: list):
    print(f"\n=== {label} ===")
    r = subprocess.run([PY, "-X", "utf8"] + args, cwd=str(HERE),
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if r.returncode != 0:
        print(f"[FAIL] {label} 返回 {r.returncode}")
        sys.exit(1)


def main():
    # 1) 自检
    run("1) 核心库自检", [str(HERE / "problem2_core_v3.py")])
    # 2) 算例 + 图
    run("2) 5 张图算例", [str(HERE / "problem2_analysis_v3.py")])
    # 3) PDF 生成
    run("3) PDF 生成", [str(HERE / "gen_problem2_pdf_v3.py")])
    # 4) 备份
    pdf = HERE / "问题二建模_v3.pdf"
    bak = HERE / "问题二建模_v3_final.pdf"
    if pdf.exists():
        shutil.copy2(str(pdf), str(bak))
        print(f"\n[备份] {bak.name}  ({bak.stat().st_size / 1024:.1f} KB)")
    print("\n[OK] 问题 2 v3 全部完成")


if __name__ == "__main__":
    main()