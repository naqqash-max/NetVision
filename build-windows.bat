@echo off
echo =====================================================================
echo NetVision Windows Desktop Builder
echo =====================================================================

REM Ensure script runs from root directory
cd %~dp0

REM Create directories
if not exist desktop\build mkdir desktop\build
if not exist desktop\dist mkdir desktop\dist

REM 1. Build Frontend
echo Building Frontend React SPA...
cd frontend
call npm install
call npm run build
cd ..

REM 2. Download Portable Python Embeddable
if not exist desktop\python_embed (
    echo Downloading Portable Python 3.11...
    powershell -Command "Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.11.5/python-3.11.5-embed-amd64.zip -OutFile desktop\python.zip"
    powershell -Command "Expand-Archive -Path desktop\python.zip -DestinationPath desktop\python_embed"
    del desktop\python.zip
    
    echo Configuring Python path...
    echo import site >> desktop\python_embed\python311._pth
    
    echo Installing pip...
    powershell -Command "Invoke-WebRequest -Uri https://bootstrap.pypa.io/get-pip.py -OutFile desktop\get-pip.py"
    desktop\python_embed\python.exe desktop\get-pip.py --no-warn-script-location
    del desktop\get-pip.py
)

REM 3. Install Python Dependencies
echo Installing build and runtime dependencies...
desktop\python_embed\python.exe -m pip install --no-warn-script-location fastapi uvicorn sqlalchemy psycopg2-binary pydantic pydantic-settings python-jose bcrypt passlib websockets python-multipart asyncpg pywebview pyinstaller scapy pysnmp-lextudio aiosnmp aioping email-validator reportlab

REM 4. Download PostgreSQL Portable
if not exist desktop\dist\NetVision\postgresql (
    echo Downloading PostgreSQL 15 Portable Binaries...
    powershell -Command "Invoke-WebRequest -Uri https://get.enterprisedb.com/postgresql/postgresql-15.3-1-windows-x64-binaries.zip -OutFile desktop\postgres.zip"
    powershell -Command "Expand-Archive -Path desktop\postgres.zip -DestinationPath desktop\postgres_temp"
    
    if not exist desktop\dist\NetVision mkdir desktop\dist\NetVision
    move desktop\postgres_temp\pgsql desktop\dist\NetVision\postgresql
    
    del desktop\postgres.zip
    rmdir /s /q desktop\postgres_temp
)

REM 5. Run PyInstaller to build executables
echo Compiling Backend Executable...
desktop\python_embed\python.exe -m PyInstaller --noconfirm --onefile --paths backend --icon=desktop\assets\netvision.ico --name backend_app --distpath desktop\dist_temp --workpath desktop\build desktop\backend_entry.py

echo Compiling Networking Engine Executable...
desktop\python_embed\python.exe -m PyInstaller --noconfirm --onefile --paths networking-engine --icon=desktop\assets\netvision.ico --name networking_engine_app --distpath desktop\dist_temp --workpath desktop\build desktop\engine_entry.py

echo Compiling Main Desktop Launcher (Requesting Administrator Elevation)...
desktop\python_embed\python.exe -m PyInstaller --noconfirm --onedir --windowed --uac-admin --icon=desktop\assets\netvision.ico --name NetVision --distpath desktop\dist_final --workpath desktop\build desktop\launcher.py

REM 6. Structure Final Package
echo Structuring NetVision Desktop Package...
xcopy /E /I /Y desktop\dist_final\NetVision\* desktop\dist\NetVision\
move /Y desktop\dist_temp\backend_app.exe desktop\dist\NetVision\
move /Y desktop\dist_temp\networking_engine_app.exe desktop\dist\NetVision\

REM Copy schema/seed
xcopy /E /I /Y database desktop\dist\NetVision\database

REM Copy built frontend SPA
xcopy /E /I /Y frontend\dist desktop\dist\NetVision\frontend\dist

REM Clean up temp folders
rmdir /s /q desktop\dist_final
rmdir /s /q desktop\dist_temp
rmdir /s /q desktop\build

echo =====================================================================
echo NetVision Desktop Build Complete!
echo Location: desktop\dist\NetVision\
echo =====================================================================
