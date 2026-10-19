@echo off
chcp 65001 >nul
title ColorHist CBIR - He thong truy xuat anh dua tren Color Histogram
echo ======================================================================
echo    HE THONG TRUY XUAT ANH DUA TREN COLOR HISTOGRAM (CBIR)
echo    Chay cuc bo tren Windows (Khong Docker, Khong Deploy)
echo ======================================================================
echo.

REM Kiem tra Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Khong tim thay Python tren he thong!
    echo Vui long cai dat Python 3.8 tro len va them vao PATH.
    pause
    exit /b
)

echo [1/3] Kiem tra va cai dat thu vien (Neu thieu)...
python -m pip install flask opencv-python pillow numpy scipy >nul 2>&1

echo [2/3] Kiem tra thu muc du lieu (Dataset)...
if not exist "dataset" (
    mkdir "dataset"
)

echo [3/3] Dang khoi dong Web Server tai http://127.0.0.1:5000 ...
echo Trinh duyet web se tu dong mo trong 2 giay...
start http://127.0.0.1:5000

python app.py
pause
