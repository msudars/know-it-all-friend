"""Streamlit knowledge explorer (``app.py``) and how to launch it."""

from __future__ import annotations

import sys
from pathlib import Path


def streamlit_command(port: int) -> list[str]:
    """Command that serves the explorer on localhost only, with Streamlit's usage stats off.

    Streamlit otherwise listens on every interface (your documents become
    reachable from the local network) and phones home usage statistics.
    """
    return [
        sys.executable, "-m", "streamlit", "run", str(Path(__file__).parent / "app.py"),
        "--server.port", str(port),
        "--server.address", "127.0.0.1",
        "--browser.gatherUsageStats", "false",
    ]
