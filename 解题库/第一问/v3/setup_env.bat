@echo off
REM v3.5.6.1 一键环境设置：限制 OpenBLAS / OMP / MKL 单线程
REM 解决 numpy + matplotlib + reportlab 同时加载时的 OpenBLAS MemoryError

set OPENBLAS_NUM_THREADS=1
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set PYTHONIOENCODING=utf-8

echo [setup_env] OpenBLAS / OMP / MKL 已限制为单线程
echo [setup_env] PYTHONIOENCODING=utf-8
echo.
echo 用法: setup_env.bat ^&^& python verify_v3.py
echo 或:    setup_env.bat ^&^& python gen_problem1_pdf_v3.py
