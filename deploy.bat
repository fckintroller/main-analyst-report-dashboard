@echo off
chcp 65001 > nul
title GitHub Pages 웹 대시보드 배포 도구

echo ==========================================================
echo       대한민국 최정상급 애널리스트 대시보드 GitHub Pages 배포
echo ==========================================================
echo.
echo [1/3] 변경된 모든 파일 스테이징 중...
git add .

echo.
echo [2/3] 변경 사항 로컬 커밋 중...
git commit -m "Auto-update analyst dashboard" > nul 2>&1

if %errorlevel% equ 0 echo   - 성공: 변경 사항이 저장되었습니다.
if %errorlevel% neq 0 echo   - 알림: 변경된 파일이 없거나 이미 최신 상태입니다.

echo.
echo [3/3] GitHub 원격 연결 및 배포 단계...

git remote get-url origin > nul 2>&1
if %errorlevel% neq 0 goto NO_REMOTE

echo   - 깃허브로 파일 업로드 중: git push origin main
git push origin main
if %errorlevel% equ 0 goto PUSH_SUCCESS

echo.
echo [에러] 파일 업로드 도중 문제가 발생했습니다.
echo - 네트워크 연결 상태 또는 깃허브 로그인 자격 증명을 확인해 주십시오.
pause
exit /b 1

:PUSH_SUCCESS
echo.
echo ==========================================================
echo ✔ 성공: 깃허브로 데이터가 성공적으로 업로드되었습니다!
echo ==========================================================
echo.
echo ----------------------------------------------------------
echo 💡 웹사이트 확인 방법 (GitHub Actions 자동 배포 설정됨)
echo ----------------------------------------------------------
echo 1. 현재 프로젝트는 GitHub Actions를 통해 'web' 폴더가 자동 배포됩니다.
echo 2. 업로드 후 약 1~2분 뒤에 자동으로 웹사이트가 갱신됩니다.
echo 3. 주소 예시: https://[귀하의깃허브ID].github.io/[저장소이름]/
echo ----------------------------------------------------------
echo.
pause
goto EOF

:NO_REMOTE
echo.
echo ----------------------------------------------------------
echo ⚠  경고: 아직 깃허브 원격 저장소가 연결되지 않았습니다!
echo ----------------------------------------------------------
echo GitHub Pages 웹 배포를 활성화하려면 아래 단계를 거쳐야 합니다:
echo.
echo ① 웹 브라우저로 깃허브에 접속하여 로그인합니다. 주소: https://github.com
echo ② 우측 상단의 + 버튼을 누르고 'New repository'를 선택합니다.
echo ③ Repository name에 'analyst-dashboard' 또는 원하는 이름을 적습니다.
echo ④ 반드시 'Public'으로 설정해야 무료 웹 호스팅이 가능합니다.
echo ⑤ 'Create repository' 버튼을 누릅니다.
echo ⑥ 생성된 페이지의 git remote add origin ... 명령어를 실행합니다.
echo.
echo 원격 저장소 주소를 추가하신 후, 본 deploy.bat를 다시 실행해 주십시오!
echo ----------------------------------------------------------
echo.
pause
exit /b 1

:EOF
