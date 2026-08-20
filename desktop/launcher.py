import os
import sys
import time
import socket
import subprocess
import logging
import random
import string
import webview

IS_BUNDLE = hasattr(sys, '_MEIPASS')
BASE_DIR = os.path.dirname(sys.executable) if IS_BUNDLE else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Define writeable user data directory (LocalAppData is standard on Windows, user home on fallback)
if IS_BUNDLE:
    APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expandvars("%LOCALAPPDATA%")), "NetVision")
else:
    APP_DATA_DIR = BASE_DIR

os.makedirs(APP_DATA_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(APP_DATA_DIR, "netvision_desktop.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("NetVisionLauncher")

def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0

def find_free_port(start_port: int) -> int:
    port = start_port
    while port < 65535:
        if is_port_free(port):
            return port
        port += 1
    raise RuntimeError("No free ports available!")

def generate_random_secret() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=32))

def get_or_create_secrets() -> tuple:
    env_file = os.path.join(APP_DATA_DIR, "config.env")
    secret_key = None
    db_password = None

    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                if line.startswith("SECRET_KEY="):
                    secret_key = line.split("=", 1)[1].strip()
                elif line.startswith("POSTGRES_PASSWORD="):
                    db_password = line.split("=", 1)[1].strip()

    updated = False
    if not secret_key:
        secret_key = generate_random_secret()
        updated = True
    if not db_password:
        db_password = generate_random_secret()
        updated = True

    if updated:
        with open(env_file, "w") as f:
            f.write(f"SECRET_KEY={secret_key}\n")
            f.write(f"POSTGRES_PASSWORD={db_password}\n")
            logger.info("Saved new secure random credentials to config.env")

    return secret_key, db_password

def main():
    logger.info("Starting NetVision Desktop Application...")
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

    # 1. Resolve ports
    db_port = find_free_port(5432)
    backend_port = find_free_port(8000)
    logger.info(f"Using free ports - Database: {db_port}, Backend API: {backend_port}")

    # 2. Get secrets
    secret_key, db_password = get_or_create_secrets()

    # 3. Locate paths
    pg_dir = os.path.join(BASE_DIR, "postgresql")
    db_data_dir = os.path.join(APP_DATA_DIR, "database_data")
    backend_executable = os.path.join(BASE_DIR, "backend_app.exe")
    engine_executable = os.path.join(BASE_DIR, "networking_engine_app.exe")

    # Fallbacks for dev mode runs
    if not IS_BUNDLE:
        pg_dir = "C:\\Program Files\\PostgreSQL\\15"  # Dev fallback path
        backend_executable = "python"
        engine_executable = "python"

    # 4. Initialize Database if required
    initdb_path = os.path.join(pg_dir, "bin", "initdb.exe")
    pg_ctl_path = os.path.join(pg_dir, "bin", "pg_ctl.exe")
    createdb_path = os.path.join(pg_dir, "bin", "createdb.exe")
    psql_path = os.path.join(pg_dir, "bin", "psql.exe")

    if IS_BUNDLE and not os.path.exists(os.path.join(db_data_dir, "PG_VERSION")):
        logger.info("Initializing portable database...")
        os.makedirs(db_data_dir, exist_ok=True)
        pw_file = os.path.join(APP_DATA_DIR, "pg_pw.txt")
        with open(pw_file, "w") as f:
            f.write(db_password)
        
        init_cmd = [initdb_path, "-D", db_data_dir, "-U", "admin", "-A", "scram-sha-256", f"--pwfile={pw_file}"]
        logger.info(f"Running initdb: {' '.join(init_cmd)}")
        subprocess.run(init_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
        
        if os.path.exists(pw_file):
            os.remove(pw_file)

    # 5. Start Database
    logger.info("Starting local database server...")
    db_cmd = [pg_ctl_path, "-D", db_data_dir, "-o", f"-h 127.0.0.1 -p {db_port}", "start"]
    if not IS_BUNDLE:
        db_cmd = [pg_ctl_path, "-D", db_data_dir, "-o", f"-h 127.0.0.1 -p {db_port}", "start"]
    
    subprocess.run(db_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)

    # Wait for database availability
    db_ready = False
    for _ in range(20):
        if not is_port_free(db_port):
            db_ready = True
            break
        time.sleep(0.5)

    if not db_ready:
        logger.fatal("Database failed to start in a timely manner.")
        webview.windows[0].destroy() if webview.windows else None
        sys.exit(1)

    logger.info("Database online.")

    # 6. Apply schema to new database if required
    # Create DB 'netvision' if not exists
    os.environ["PGPASSWORD"] = db_password
    try:
        # Check if database exists
        check_db = subprocess.run(
            [psql_path, "-h", "127.0.0.1", "-p", str(db_port), "-U", "admin", "-lqt"],
            capture_output=True, text=True, creationflags=creation_flags
        )
        if "netvision" not in check_db.stdout:
            logger.info("Creating 'netvision' database...")
            subprocess.run([createdb_path, "-h", "127.0.0.1", "-p", str(db_port), "-U", "admin", "netvision"], creationflags=creation_flags)
            
             # Apply schema.sql
            schema_file = os.path.join(BASE_DIR, "database", "schema.sql")
            seed_file = os.path.join(BASE_DIR, "database", "seed.sql")
            seed_dev_user_file = os.path.join(BASE_DIR, "database", "seed_dev_user.sql")
            if os.path.exists(schema_file):
                logger.info("Applying schema.sql...")
                subprocess.run([psql_path, "-h", "127.0.0.1", "-p", str(db_port), "-U", "admin", "-d", "netvision", "-f", schema_file], creationflags=creation_flags)
            
            # Seed data is development/demo only, disabled in production installs
            if not IS_BUNDLE:
                if os.path.exists(seed_file):
                    logger.info("Applying seed.sql (development mode)...")
                    subprocess.run([psql_path, "-h", "127.0.0.1", "-p", str(db_port), "-U", "admin", "-d", "netvision", "-f", seed_file], creationflags=creation_flags)
                if os.path.exists(seed_dev_user_file):
                    logger.info("Applying seed_dev_user.sql (development mode)...")
                    subprocess.run([psql_path, "-h", "127.0.0.1", "-p", str(db_port), "-U", "admin", "-d", "netvision", "-f", seed_dev_user_file], creationflags=creation_flags)
    except Exception as ex:
        logger.error(f"Error initializing schema: {ex}")

    # 7. Start FastAPI Backend
    logger.info("Starting API Backend...")
    db_url = f"postgresql://admin:{db_password}@127.0.0.1:{db_port}/netvision"
    
    backend_env = os.environ.copy()
    backend_env["DATABASE_URL"] = db_url
    backend_env["SECRET_KEY"] = secret_key
    backend_env["ENVIRONMENT"] = "production"
    backend_env["FRONTEND_URL"] = f"http://127.0.0.1:{backend_port}"
    backend_env["EMAIL_ENABLED"] = "false"
    backend_env["BACKEND_CORS_ORIGINS"] = f"[\"http://127.0.0.1:{backend_port}\"]"



    if IS_BUNDLE:
        backend_proc = subprocess.Popen(
            [backend_executable],
            env=backend_env,
            creationflags=creation_flags
        )
    else:
        # Dev run
        backend_proc = subprocess.Popen(
            [backend_executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(backend_port)],
            cwd=os.path.join(BASE_DIR, "backend"),
            env=backend_env,
            creationflags=creation_flags
        )

    # Wait for backend
    backend_ready = False
    for _ in range(20):
        if not is_port_free(backend_port):
            backend_ready = True
            break
        time.sleep(0.5)

    if not backend_ready:
        logger.fatal("Backend API failed to start.")
        # Stop DB
        subprocess.run([pg_ctl_path, "-D", db_data_dir, "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
        sys.exit(1)

    logger.info("Backend API online.")

    # 8. Start Networking Engine
    logger.info("Starting Background Networking Engine...")
    engine_env = os.environ.copy()
    engine_env["DATABASE_URL"] = db_url
    engine_env["MONITOR_CONCURRENCY_LIMIT"] = "10"

    if IS_BUNDLE:
        engine_proc = subprocess.Popen(
            [engine_executable],
            env=engine_env,
            creationflags=creation_flags
        )
    else:
        engine_proc = subprocess.Popen(
            [engine_executable, "main.py"],
            cwd=os.path.join(BASE_DIR, "networking-engine"),
            env=engine_env,
            creationflags=creation_flags
        )

    # 9. Launch Native UI Window
    logger.info("Launching user interface window...")
    window = webview.create_window(
        title="NetVision Operations Center",
        url=f"http://127.0.0.1:{backend_port}",
        width=1280,
        height=800,
        resizable=True
    )

    # Register clean shutdown callbacks
    def on_closed():
        logger.info("UI Window closed. Shutting down child processes...")
        
        # Kill backend
        try:
            backend_proc.terminate()
            backend_proc.wait(timeout=2)
        except Exception:
            backend_proc.kill()

        # Kill engine
        try:
            engine_proc.terminate()
            engine_proc.wait(timeout=2)
        except Exception:
            engine_proc.kill()

        # Stop PostgreSQL
        logger.info("Shutting down database...")
        subprocess.run([pg_ctl_path, "-D", db_data_dir, "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
        logger.info("NetVision Desktop shutdown complete.")

    window.events.closed += on_closed
    webview.start()

if __name__ == "__main__":
    main()
