@echo off
REM Gera o instalador do SIGM Web (substitui o SIGM desktop).
REM Requisitos: Python com as dependencias do requirements.txt, PyInstaller e Inno Setup 6.
setlocal
cd /d "%~dp0"

if /i "%~1"=="so-instalador" goto inno

echo [1/3] Testes...
python -m unittest discover -s tests >nul 2>&1
if errorlevel 1 (
  echo Alguns testes falharam ou nao puderam rodar. Rode "python -m unittest discover -s tests" para ver.
  choice /m "Continuar mesmo assim"
  if errorlevel 2 exit /b 1
)

echo [2/3] Empacotando com PyInstaller...
if exist build rmdir /s /q build
if exist dist\SIGM rmdir /s /q dist\SIGM
python -m PyInstaller SIGM_WEB.spec --noconfirm
if errorlevel 1 (echo Falha no PyInstaller. & exit /b 1)


:inno
echo [3/3] Criando o instalador com Inno Setup...
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do (
  if exist %%P set "ISCC=%%~P"
)
if not defined ISCC (
  for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do set "ISCC=%%I"
)
if not defined ISCC (
  for %%K in ("HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall" "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall") do (
    for /f "tokens=2*" %%A in ('reg query "%%~K\Inno Setup 6_is1" /v InstallLocation 2^>nul') do (
      if exist "%%B\ISCC.exe" set "ISCC=%%B\ISCC.exe"
    )
  )
)
if not defined ISCC (
  echo Inno Setup 6 nao encontrado. Instale em https://jrsoftware.org/isdl.php e rode este arquivo de novo.
  echo Se ja instalou, localize com: Get-ChildItem C:\ -Filter ISCC.exe -Recurse -ErrorAction SilentlyContinue ^| Select -First 3 FullName
  echo O programa ja foi empacotado em dist\SIGM. Depois de instalar o Inno Setup, rode: gerar_instalador_web.bat so-instalador
  exit /b 1
)
"%ISCC%" instalador\SIGM_Web_Setup.iss
if errorlevel 1 (echo Falha no Inno Setup. & exit /b 1)

echo.
echo Pronto: instalador\output\SIGM_Setup_2.1.4_Web.exe
endlocal
