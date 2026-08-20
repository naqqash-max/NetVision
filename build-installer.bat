@echo off
echo =====================================================================
echo NetVision Windows Desktop Installer Builder
echo =====================================================================

REM Ensure script runs from root directory
cd %~dp0

REM 1. Build the desktop application
echo Step 1: Building the desktop application...
call build-windows.bat

REM 2. Verify the generated NetVision.exe
echo.
echo Step 2: Verifying desktop application build...
if not exist desktop\dist\NetVision\NetVision.exe (
    echo [ERROR] NetVision.exe was not created successfully! Build failed.
    exit /b 1
)
echo Verification successful: NetVision.exe is present.

REM 3. Build the Windows installer using Inno Setup
echo.
echo Step 3: Compiling Windows Installer (Inno Setup)...
if not exist dist\installer mkdir dist\installer

REM Locate Inno Setup Compiler
set "ISCC_PATH=C:\Users\Naqqash\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
if exist "%ISCC_PATH%" goto run_compiler

where iscc >nul 2>&1
if %errorlevel% equ 0 (
    set "ISCC_PATH=iscc"
    goto run_compiler
)

echo [ERROR] Inno Setup compiler (ISCC.exe) not found at:
echo "%ISCC_PATH%"
echo Please ensure Inno Setup is installed properly.
exit /b 1

:run_compiler
echo Using ISCC compiler: "%ISCC_PATH%"
cd desktop
"%ISCC_PATH%" netvision.iss
cd ..

REM 4. Verify the final installer
echo.
echo Step 4: Verifying installer executable...
if not exist dist\installer\NetVision-Setup.exe (
    echo [ERROR] Installer was not created successfully! Build failed.
    exit /b 1
)

echo =====================================================================
echo NetVision Windows Installer Build Complete!
echo Location: dist\installer\NetVision-Setup.exe
echo =====================================================================
