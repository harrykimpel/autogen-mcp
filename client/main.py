from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    """Launch the Streamlit client with proper ScriptRunContext."""
    try:
        from streamlit.web.cli import main as streamlit_main
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Streamlit is required to run the client.") from exc

    app_path = Path(__file__).with_name("client.py")
    sys.argv = ["streamlit", "run", str(app_path)]

    # Preserve MCP_SERVER_URL env var if set
    if "MCP_SERVER_URL" in os.environ:
        os.environ["MCP_SERVER_URL"] = os.environ["MCP_SERVER_URL"]

    streamlit_main()


__all__ = ["main"]
