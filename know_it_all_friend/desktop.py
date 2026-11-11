"""Desktop application wrapper (Phase 14)."""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import time
from contextlib import closing

# qtpy prefers PyQt5 when both bindings are installed, but our webengine dep is
# PyQt6 — pin the API before pywebview imports qtpy.
os.environ.setdefault("QT_API", "pyqt6")

try:
    import webview
    _WEBVIEW_AVAILABLE = True
except ImportError:
    _WEBVIEW_AVAILABLE = False

logger = logging.getLogger(__name__)

def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False

def start_desktop() -> None:
    """Launch the Streamlit app in a native desktop window using pywebview."""
    from know_it_all_friend.ui import streamlit_command

    port = _find_free_port()

    logger.info("Starting background Streamlit server on port %d...", port)

    # Launch Streamlit as a headless background process
    process = subprocess.Popen(
        streamlit_command(port) + ["--server.headless", "true"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if not _wait_for_server(port):
        process.terminate()
        process.wait()
        logger.error("Streamlit server did not start on port %d.", port)
        raise SystemExit(1)

    url = f"http://127.0.0.1:{port}"
    logger.info("Opening interface at %s", url)

    if _WEBVIEW_AVAILABLE:
        try:
            webview.create_window(
                title="Know-it-all Friend",
                url=url,
                width=1200,
                height=800,
            )
            webview.start()
        finally:
            logger.info("Desktop window closed. Shutting down background server...")
            process.terminate()
            process.wait()
    else:
        # Fallback: open in default browser
        import webbrowser
        webbrowser.open(url)
        logger.info(
            "Opened in your browser (native window needs the [desktop] extra). "
            "Press Ctrl+C to stop the server."
        )
        try:
            process.wait()
        finally:
            logger.info("Server process terminated.")
