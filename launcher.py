"""Windows executable launcher for GeoProfiler."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
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
    env = build_environment(runtime_root)
    command = build_streamlit_command(app_path, port)

    process = subprocess.Popen(
        command,
        cwd=str(project_root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=get_subprocess_flags(),
    )

    url = f"http://localhost:{port}"
    wait_for_server("127.0.0.1", port)
    webbrowser.open(url)

    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()


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


def build_environment(runtime_root: Path) -> dict[str, str]:
    """Build environment variables used by the Streamlit process."""
    env = os.environ.copy()
    env["GEOPROFILER_RUNTIME_DIR"] = str(runtime_root)
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    return env


def build_streamlit_command(app_path: Path, port: int) -> list[str]:
    """Build the command that starts Streamlit."""
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]


def find_available_port(start_port: int) -> int:
    """Find an available localhost port starting at the preferred port."""
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port

    raise RuntimeError("Nenhuma porta local disponivel para iniciar o GeoProfiler.")


def wait_for_server(host: str, port: int, timeout_seconds: int = 25) -> None:
    """Wait briefly for Streamlit to start before opening the browser."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.4)


def get_subprocess_flags() -> int:
    """Return Windows subprocess flags when available."""
    if os.name != "nt":
        return 0

    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


if __name__ == "__main__":
    main()
