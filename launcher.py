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

# Imported eagerly, at module load time (before any thread exists), so that
# the main thread's later `import streamlit...` calls in run_streamlit() and
# the watchdog thread's own import below both hit an already-fully-loaded
# module instead of racing to import the streamlit package for the first
# time concurrently. Two threads doing that at once triggers a genuine
# CPython import-lock deadlock (reproduced empirically: `_DeadlockError` from
# `_ModuleLock('streamlit.config')` when the watchdog thread's import ran
# concurrently with run_streamlit()'s).
from streamlit.runtime.runtime import Runtime, RuntimeState  # noqa: E402


APP_FILE = "app.py"
DEFAULT_PORT = 8501

# How often to check whether the browser is still connected, and how long to
# wait after the last tab disconnects before treating that as "the user
# closed the app" (long enough to survive a manual page refresh).
CONNECTION_POLL_INTERVAL_SECONDS = 2
IDLE_SHUTDOWN_GRACE_SECONDS = 10


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
    threading.Thread(target=shutdown_when_browser_closes, daemon=True).start()

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


def shutdown_when_browser_closes() -> None:
    """Exit the process once the browser window has been closed.

    Streamlit's server has no built-in concept of "the browser was closed":
    closing the tab just drops the websocket connection, and the headless
    `--noconsole` process otherwise keeps running invisibly in the
    background forever. Streamlit's own Runtime does track connected
    sessions internally (that's how it decides whether to keep a session's
    state alive across a page refresh), so this polls that state to detect
    "last session disconnected" reliably.

    Detection is solid, but a graceful `Runtime.stop()` is not enough to
    actually end the process: it stops Streamlit's internal session loop
    (confirmed empirically - the Runtime's state does reach `STOPPED` within
    a second), but the underlying Uvicorn/ASGI server that owns the listening
    socket keeps running regardless, so the process lingers forever. Once the
    disconnect grace period elapses, this hard-exits the process directly
    instead. That's safe here: every case/crime write already commits to
    SQLite synchronously within its own Streamlit script run, well before the
    browser could be closed, so there's no in-flight state to flush on exit.
    """
    while not Runtime.exists():
        time.sleep(CONNECTION_POLL_INTERVAL_SECONDS)

    runtime = Runtime.instance()

    while runtime.state != RuntimeState.ONE_OR_MORE_SESSIONS_CONNECTED:
        time.sleep(CONNECTION_POLL_INTERVAL_SECONDS)

    disconnected_since: float | None = None
    while True:
        time.sleep(CONNECTION_POLL_INTERVAL_SECONDS)
        if runtime.state == RuntimeState.NO_SESSIONS_CONNECTED:
            disconnected_since = disconnected_since or time.time()
            if time.time() - disconnected_since >= IDLE_SHUTDOWN_GRACE_SECONDS:
                os._exit(0)
        else:
            disconnected_since = None


if __name__ == "__main__":
    main()
