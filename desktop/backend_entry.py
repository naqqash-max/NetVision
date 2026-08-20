import uvicorn
import os
import sys

# Append backend directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(current_dir, "..", "backend")))

from app.main import app

if __name__ == "__main__":
    # Get port dynamically, defaulting to 8000
    # On desktop, the launcher runs uvicorn directly
    port = int(os.environ.get("FRONTEND_URL", "http://127.0.0.1:8000").split(":")[-1])
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
