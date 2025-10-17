"""Streamlit client for interacting with the MCP testing server."""

import json
import os
from typing import Any, Dict, List, cast

import httpx
import streamlit as st

DEFAULT_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8080")
HEALTH_ENDPOINT = "/health"
CHAT_ENDPOINT = "/chat"


@st.cache_resource(show_spinner=False)
def _get_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(10.0))


def ping_server(base_url: str) -> bool:
    client = _get_client()
    try:
        response = client.get(f"{base_url.rstrip('/')}{HEALTH_ENDPOINT}")
        response.raise_for_status()
    except httpx.HTTPError:
        return False
    return True


def send_message(base_url: str, message: str) -> Dict[str, Any]:
    client = _get_client()
    response = client.post(
        f"{base_url.rstrip('/')}{CHAT_ENDPOINT}",
        json={"message": message},
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    return response.json()


def render_sidebar() -> str:
    st.sidebar.header("Server settings")
    base_url = st.sidebar.text_input(
        "Server URL",
        value=DEFAULT_SERVER_URL,
        help="Base URL for the FastAPI MCP server (e.g. http://localhost:8080)",
    )

    status_placeholder = st.sidebar.empty()
    if st.sidebar.button("Check health"):
        healthy = ping_server(base_url)
        if healthy:
            status_placeholder.success("Server is healthy")
        else:
            status_placeholder.error("Server check failed")

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Set MCP_SERVER_URL env var to override the default."
    )

    return base_url


def render_chat(base_url: str) -> None:
    st.title("MCP Testing Client")
    st.caption("Chat with the orchestrator backed by MCP tools.")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    chat_history = cast(List[Dict[str, str]], st.session_state["chat_history"])

    for entry in chat_history:
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])

    if user_input := st.chat_input("Ask me anything..."):
        chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            with st.spinner("Waiting for server response..."):
                try:
                    payload = send_message(base_url, user_input)
                except httpx.HTTPError as exc:
                    error_message = f"Request failed: {exc}"
                    response_placeholder.error(error_message)
                    chat_history.append({"role": "assistant", "content": error_message})
                else:
                    answer = payload.get("response", "(no response)")
                    
                    # Handle MCP-style content blocks if they weren't cleaned server-side
                    if isinstance(answer, str) and answer.startswith('[{"type":'):
                        try:
                            blocks = json.loads(answer)
                            if isinstance(blocks, list):
                                text_parts = [
                                    block.get("text", "")
                                    for block in blocks
                                    if isinstance(block, dict) and block.get("type") == "text"
                                ]
                                answer = "".join(text_parts) if text_parts else answer
                        except Exception:
                            pass  # Keep original answer if parsing fails
                    
                    response_placeholder.markdown(answer)
                    chat_history.append({"role": "assistant", "content": answer})


def main() -> None:
    base_url = render_sidebar()
    render_chat(base_url)


if __name__ == "__main__":
    main()
