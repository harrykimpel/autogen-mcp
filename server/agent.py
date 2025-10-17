from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import SseMcpToolAdapter, SseServerParams
import click
from dataclasses import dataclass
from fastapi import FastAPI
import logging
import os
from pydantic import BaseModel
from typing import Any, Dict
import uuid
import time

from util.llm_utils import get_llm_model
import uvicorn

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


def get_tool_hostname() -> str:
    return os.getenv("TOOL_HOSTNAME", "localhost")


def get_tool_port() -> int:
    return int(os.getenv("TOOL_PORT", 8090))


def get_tool_url() -> str:
    return f"http://{get_tool_hostname()}:{get_tool_port()}/sse"


def get_openai_base_url() -> str:
    return os.getenv("OPENAI_BASE_URL", "")


@dataclass
class ChatData(BaseModel):
    message: str


@click.command()
@click.option("--port", default=8080, help="Port to listen on for SSE")
def main(port: int):
    # Configure logging (only if not already configured by parent process)
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
    logger: logging.Logger = logging.getLogger("server")
    logger.debug("Starting main() entrypoint", extra={"port": port})

    app = FastAPI(title="Chat API")

    async def create_agent(request_id: str) -> AssistantAgent:
        start_ts = time.time()
        logger.debug("[create_agent] Begin", extra={"request_id": request_id})
        # Create server params for the remote MCP service
        server_params = SseServerParams(
            url=get_tool_url(),
            headers={"Content-Type": "application/json"},
            timeout=5,  # Connection timeout in seconds
        )
        logger.debug("[create_agent] Connecting to MCP tools", extra={"request_id": request_id, "tool_url": get_tool_url()})
        calculator_adapter = await SseMcpToolAdapter.from_server_params(server_params, "calculator")
        weather_adapter = await SseMcpToolAdapter.from_server_params(server_params, "get_weather")
        file_reader_adapter = await SseMcpToolAdapter.from_server_params(server_params, "read_file")
        logger.info(
            "[create_agent] Tools initialized",
            extra={"request_id": request_id, "tools": ["calculator", "get_weather", "read_file"]},
        )

        from typing import Sequence
        tools: Sequence = [calculator_adapter, file_reader_adapter, weather_adapter]

        # Create model client
        model_name = get_llm_model()
        base_url = get_openai_base_url()
        client_kwargs: Dict[str, Any] = {"model": model_name}
        if base_url:
            client_kwargs["base_url"] = base_url

        logger.info(
            "Initializing OpenAIChatCompletionClient",
            extra={"request_id": request_id, "model": model_name, "base_url": base_url or "default"},
        )

        model_client = OpenAIChatCompletionClient(**client_kwargs)
        
        # Create a single agent with access to all tools
        agent = AssistantAgent(
            name="assistant",
            model_client=model_client,
            tools=tools, # type: ignore
            system_message=(
                "You are a helpful AI assistant with access to the following tools:\n"
                "1. calculator - Perform arithmetic operations (add, subtract, multiply, divide)\n"
                "2. get_weather - Get current weather information for any city\n"
                "3. read_file - Read contents of files from the data directory\n\n"
                "Analyze the user's request and use the appropriate tool(s) to help them. "
                "You can use multiple tools if needed to complete the task."
            ),
        )
        elapsed = time.time() - start_ts
        logger.debug("[create_agent] Complete", extra={"request_id": request_id, "elapsed_ms": int(elapsed * 1000)})
        return agent


    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    @app.post("/chat")
    async def chat(request: ChatData):
        request_id = str(uuid.uuid4())
        t0 = time.time()
        # Avoid using reserved LogRecord attribute names (e.g. 'message') in 'extra'
        logger.info("[chat] Received request", extra={"request_id": request_id, "user_message": request.message})
        agent = await create_agent(request_id)

        # Run the agent with the user's message
        logger.debug("[chat] Starting agent.run", extra={"request_id": request_id})
        result = await agent.run(task=request.message)
        logger.debug("[chat] agent.run completed", extra={"request_id": request_id})
        # Log only lightweight metadata about the TaskResult to prevent large payloads
        logger.info(
            "chat result from agent run",
            extra={
                "request_id": request_id,
                "result_type": result.__class__.__name__,
                "message_count": len(getattr(result, "messages", []) or []),
            },
        )

        # Extract the response
        response_text = ""
        if hasattr(result, "messages") and result.messages:
            last_message = result.messages[-1]
            content = getattr(last_message, "content", None)

            if content is not None:
                if isinstance(content, str):
                    response_text = content
                elif isinstance(content, list):
                    # Handle content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    response_text = "".join(text_parts) if text_parts else str(content)
                else:
                    response_text = str(content)

        duration_ms = int((time.time() - t0) * 1000)
        logger.info(
            "[chat] Completed",
            extra={
                "request_id": request_id,
                "user_message": request.message,
                "response": response_text,
                "duration_ms": duration_ms,
            },
        )
        return {"request_id": request_id, "message": request.message, "response": response_text, "duration_ms": duration_ms}


    uvicorn.run(app, port=port)


if __name__ == "__main__":
    import newrelic.agent

    # Initialize New Relic Python Agent
    newrelic.agent.initialize("../newrelic.ini")
    newrelic.agent.register_application(timeout=10)

    main()