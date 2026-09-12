#!/usr/bin/env bash
# v3 一键跑：核心库自检 + 算例与可视化 + PDF 生成
set -e
cd "$(dirname "$0")"
echo "[1/3] 核心库自检 ..."
python problem1_core_v3.py
echo "[2/3] 算例与可视化 ..."
python problem2_analysis_v3.py
echo "[3/3] PDF 生成 ..."
python gen_problem1_pdf_v3.py
echo "完成。产物："
echo "  - problem1_v3_results.json"
echo "  - figures/*.png"
echo "  - 问题一建模_v3.pdf"
