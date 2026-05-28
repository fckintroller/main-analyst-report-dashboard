@echo off
title GitHub Pages 웹 대시보드 배포 도구

echo ==========================================================
echo       대한민국 최정상급 애널리스트 대시보드 GitHub Pages 배포
echo ==========================================================
echo.
echo [1/3] 변경된 모든 웹 파일 스테이징 중...
git add .

:: 날짜/시간 포맷 생성
set TIMESTAMP=%date% %time%

echo.
echo [2/3] 변경 사항 로컬 커밋 중...
git commit -m "Auto-update analyst dashboard" > nul 2>&1

:: 성공/실패 여부를 단일 행으로 분기 처리 (괄호 충돌 원천 차단)
if %errorlevel% equ 0 echo   - 성공: 변경 사항이 저장되었습니다.
if %errorlevel% neq 0 echo   - 알림: 변경된 파일이 없거나 이미 최신 상태입니다.

echo.
echo [3/3] GitHub 원격 연결 및 배포 단계...

:: 원격 저장소 존재 여부 판별
git remote get-url origin > nul 2>&1
if %errorlevel% neq 0 goto NO_REMOTE

:: 원격지가 설정된 경우 즉시 push 시행
echo   - 깃허브로 파일 업로드 중: git push origin main
git push origin main
if %errorlevel% equ 0 goto PUSH_SUCCESS

:: 푸시 실패 시 안내
echo.
echo [에러] 파일 업로드 도중 문제가 발생했습니다.
echo - 네트워크 연결 상태 또는 깃허브 로그인 자격 증명을 확인해 주십시오.
pause
exit /b 1

:PUSH_SUCCESS
echo.
echo ==========================================================
echo ?? 성공: 깃허브로 대시보드가 성공적으로 배포되었습니다!
echo ==========================================================
echo.
echo ----------------------------------------------------------
echo ?? 웹사이트 확인 및 공유 방법
echo ----------------------------------------------------------
echo 1. 깃허브 저장소 페이지의 Settings - Pages 탭으로 이동합니다.
echo 2. Build and deployment의 Source가 'Deploy from a branch'인지 확인합니다.
echo 3. Branch를 main 및 루트폴더로 선택하고 Save를 누릅니다.
echo 4. 약 1~2분 후, 상단에 배포 완료 주소가 표시됩니다!
echo    공유 주소 예시: https://[귀하의깃허브ID].github.io/[저장소이름]/
echo ----------------------------------------------------------
echo.
pause
goto EOF

:NO_REMOTE
echo.
echo ----------------------------------------------------------
echo ??  경고: 아직 깃허브 원격 저장소가 연결되지 않았습니다!
echo ----------------------------------------------------------
echo GitHub Pages 웹 배포를 활성화하려면 아래 단계를 거쳐야 합니다:
echo.
echo ① 웹 브라우저로 깃허브에 접속하여 로그인합니다. 주소: https://github.com
echo ② 우측 상단의 + 버튼을 누르고 'New repository'를 선택합니다.
echo ③ Repository name에 'analyst-dashboard' 또는 원하는 이름을 적습니다.
echo ④ 중요: 반드시 'Public'으로 설정해야 무료 웹 호스팅이 가능합니다.
echo ⑤ 'Initialize this repository with' 아래 항목들은 모두 해제된 상태로
echo    하단의 Create repository 버튼을 누릅니다.
echo ⑥ 생성된 페이지 중간의 'or push an existing repository from the command line'
echo    아래에 나오는 첫 번째 git remote 주소 명령어를 복사하여 실행합니다:
echo.
echo    실행할 명령어 예시:
echo    git remote add origin https://github.com/깃허브ID/저장소이름.git
echo.
echo ⑦ 원격 저장소 주소를 추가하신 후, 본 deploy.bat를 다시 실행해 주십시오!
echo ----------------------------------------------------------
echo.
pause
exit /b 1

:EOF
