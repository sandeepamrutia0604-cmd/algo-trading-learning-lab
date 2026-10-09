"""Starts the Algo Trading Learning Lab as a normal Windows program, for the downloadable build.

Double-click AlgoTradingLab.exe (or run `python desktop/launcher.py` from the repo): it picks a free
port, starts the app on this computer only, and opens your browser. A console window stays open while
it runs: close it (or press Ctrl+C) to quit. If the app is already running, it just opens the browser
on that copy instead of starting a second one.

Desktop mode (see backend/app/paths.py) means: simulated stocks plus CSV files only, no broker is ever
contacted, no .env is read, and your database lives in %LOCALAPPDATA%\\AlgoTradingLab.

    python desktop/launcher.py [--port 8000] [--no-browser]
"""

import argparse
import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

os.environ.setdefault("ALGO_DESKTOP", "1")  # before anything imports backend.app.config
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # running from the repo, not frozen

APP_NAME = "Algo Trading Learning Lab"
FIRST_PORT = 8000
PORT_TRIES = 20


def health(port: int) -> dict | None:
    """The app's /api/health answer on this port, or None if nothing (or something else) is there."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.5) as reply:
            return json.load(reply)
    except Exception:
        return None


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def pick_port(first: int):
    """('running', port) if this app already answers on one of the ports, else ('free', port)."""
    for port in range(first, first + PORT_TRIES):
        answer = health(port)
        if answer and answer.get("app") == APP_NAME:
            return "running", port
        if answer is None and port_is_free(port):
            return "free", port
    raise SystemExit(f"Ports {first} to {first + PORT_TRIES - 1} are all busy. Close something and try again.")


def open_when_ready(port: int, open_browser: bool) -> None:
    for _ in range(120):  # up to a minute: the very first start builds the database
        if health(port):
            break
        time.sleep(0.5)
    else:
        return
    url = f"http://127.0.0.1:{port}"
    print(f"\n{APP_NAME} is running at {url}", flush=True)
    print("Leave this window open while you use it. Close it (or press Ctrl+C) to quit.\n", flush=True)
    if open_browser:
        webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Run the {APP_NAME} on this computer.")
    parser.add_argument("--port", type=int, default=FIRST_PORT)
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser")
    args = parser.parse_args()

    state, port = pick_port(args.port)
    if state == "running":
        url = f"http://127.0.0.1:{port}"
        print(f"{APP_NAME} is already running at {url}. Opening it.")
        if not args.no_browser:
            webbrowser.open(url)
        return

    from backend.app.paths import data_dir

    folder = data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            RotatingFileHandler(folder / "app.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    print(f"Starting {APP_NAME}... (your data is in {folder})", flush=True)
    threading.Thread(target=open_when_ready, args=(port, not args.no_browser), daemon=True).start()

    import uvicorn

    from backend.app.main import app

    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_config=None)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
