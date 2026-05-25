"""Windows executable launcher for GeoProfiler."""

from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


APP_FILE = "app.py"
DEFAULT_PORT = 8501


def main() -> None:
    """Start the bundled Streamlit application and open it in the browser."""
    project_root = get_project_root()
    runtime_root = get_runtime_root()
    ensure_runtime_data(project_root, runtime_root)

    port = find_available_port(DEFAULT_PORT)
    app_path = project_root / APP_FILE
    configure_environment(runtime_root)

    url = f"http://localhost:{port}"
    threading.Thread(
        target=open_browser_when_ready,
        args=("127.0.0.1", port, url),
        daemon=True,
    ).start()

    run_streamlit(app_path, port)


def get_project_root() -> Path:
    """Return the project root for source mode or PyInstaller mode."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]

    return Path(__file__).resolve().parent


def get_runtime_root() -> Path:
    """Return a writable runtime directory for persistent project files."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def ensure_runtime_data(project_root: Path, runtime_root: Path) -> None:
    """Ensure data files exist in a writable location."""
    source_data = project_root / "data"
    runtime_data = runtime_root / "data"
    runtime_data.mkdir(parents=True, exist_ok=True)

    source_csv = source_data / "crimes.csv"
    runtime_csv = runtime_data / "crimes.csv"

    if source_csv.exists() and not runtime_csv.exists():
        shutil.copy2(source_csv, runtime_csv)


def configure_environment(runtime_root: Path) -> None:
    """Configure environment variables used by Streamlit and the app."""
    os.environ["GEOPROFILER_RUNTIME_DIR"] = str(runtime_root)
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"


def run_streamlit(app_path: Path, port: int) -> None:
    """Run Streamlit in-process to avoid executable recursion."""
    import streamlit.config as config
    from streamlit.web import bootstrap

    config.set_option("global.developmentMode", False)
    config.set_option("server.headless", True)
    config.set_option("server.port", port)
    config.set_option("server.fileWatcherType", "none")
    config.set_option("browser.gatherUsageStats", False)

    flag_options = {
        "server.port": port,
        "server.headless": True,
        "server.fileWatcherType": "none",
        "browser.gatherUsageStats": False,
        "global.developmentMode": False,
    }
    bootstrap.run(str(app_path), False, [], flag_options)


def find_available_port(start_port: int) -> int:
    """Find an available localhost port starting at the preferred port."""
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port

    raise RuntimeError("Nenhuma porta local disponivel para iniciar o GeoProfiler.")


def wait_for_server(host: str, port: int, timeout_seconds: int = 25) -> bool:
    """Wait briefly for Streamlit to start before opening the browser."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.4)
    return False


def open_browser_when_ready(host: str, port: int, url: str) -> None:
    """Open the browser once when the local Streamlit server is ready."""
    if wait_for_server(host, port):
        if os.environ.get("GEOPROFILER_NO_BROWSER") == "1":
            return
        webbrowser.open_new(url)


if __name__ == "__main__":
    main()
