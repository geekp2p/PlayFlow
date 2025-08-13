@echo off
chcp 437>nul
setlocal enabledelayedexpansion

REM — 1) แสดงโครงสร้างโฟลเดอร์ + ไฟล์ทั้งหมด
echo.
echo ===== Folder structure (tree /f) =====
tree /f
echo.

REM — รวมแพทเทิร์นไฟล์ที่ต้องการอ่านเนื้อหา
set "PATTERNS=docker-compose.yml .env core.py docker-entrypoint.sh Dockerfile start.sh emu-33-playstore.ini emu.log droidflow.log"

REM — 2) แสดงเนื้อหาไฟล์ในโฟลเดอร์หลัก (root)
echo.
echo ===== Displaying root contents =====
echo.
for %%P in (%PATTERNS%) do (
  for %%F in (%%P) do (
    if exist "%%~fF" (
      echo ------------------------------------------------------------
      echo File: %%~fF
      echo ------------------------------------------------------------
      powershell -NoLogo -NoProfile -Command "Get-Content -LiteralPath '%%~fF' | ForEach-Object { Write-Host $_ }"
      echo.
    )
  )
)

REM — 3) แสดงเนื้อหาไฟล์ในทุกโฟลเดอร์ย่อย
echo.
echo ===== Displaying subfolder contents =====
echo.
for /D /R %%D in (*) do (
  for %%P in (%PATTERNS%) do (
    if exist "%%D\%%P" (
      echo ------------------------------------------------------------
      echo File: %%D\%%P
      echo ------------------------------------------------------------
      powershell -NoLogo -NoProfile -Command "Get-Content -LiteralPath '%%D\%%P' | ForEach-Object { Write-Host $_ }"
      echo.
    )
  )
)

endlocal
