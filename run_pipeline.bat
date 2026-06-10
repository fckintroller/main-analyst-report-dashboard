@echo off
cd /d "C:\claude cowork\01_projects\Anal_reports"

:: 환경변수 로드 (API 키 등)
if exist env.bat call env.bat

echo Starting Quant Pipeline...
python scripts\pipeline.py
echo Pipeline Finished!
