# autogen with mcp testing

Example MCP client, tools server, and single-agent FastAPI service using GitHub Models.

## Quick Start

### 1. Prerequisites
* Python >= 3.10
* [uv](https://github.com/astral-sh/uv) installed (fast dependency resolver)

### 2. Clone & Install
```
git clone <your fork or repo url>
cd mcp-testing
uv sync  # installs dependencies from pyproject.toml
```

### 3. Environment Files
Copy the example and tailor as needed:
```
cp .env.example server/.env
cp .env.example tools/.env
```
Edit each `.env` to add your `OPENAI_API_KEY` (GitHub PAT with models.read). Optional: add `OPENWEATHER_API_KEY` for weather tool.

### 4. Run Services
Start the tools server first (default port 8090):
```
uv run mcp-test-tools
```
In a second terminal start the API server (default port 8080):
```
uv run mcp-test-server
```
Optional Streamlit client (if present):
```
uv run mcp-test-client
```
Or launch everything via helper:
```
uv run run-all
```

### 5. Test Endpoint
```
curl -s localhost:8080/health | jq
curl -s -X POST localhost:8080/chat -H 'Content-Type: application/json' -d '{"message":"add 3 and 5"}' | jq
```

## Server

The server is the entry point to the system. External requests will interact
with the server via REST. The server will include an agentic orchestrator
that has access to multiple tools. The tools are available in a separate
service that is accessible via MCP.

### LLM Client

The application targets GitHub Models through the OpenAI-compatible API endpoint.
Change the model for all components via `LLM_MODEL` (default: `gpt-4.1-mini`).
Requests are made using the official `openai` Python SDK pointed at the GitHub Models base URL.

### Tools

Tools run in a separate FastMCP process exposed over Server-Sent Events (SSE):

Current tools:
1. `calculator` – basic arithmetic (add/subtract/multiply/divide)
2. `get_weather` – fetch current weather for a city using OpenWeather API (needs `OPENWEATHER_API_KEY`)
3. `read_file` – read a text file from the local `data/` directory (safe path checking)

Each tool logs start, end, latency, and errors with a generated `request_id`.

### Configuration

Both the `server` and `tools` processes load environment variables from a `.env` file.

Minimum required variables for GitHub Models:

```
OPENAI_API_KEY=<your GitHub personal access token with models.read>
# Optional overrides:
OPENAI_BASE_URL=https://models.inference.ai.azure.com
LLM_MODEL=gpt-4.1-mini
```

Notes:
* `OPENAI_BASE_URL` defaults internally if omitted.
* You can swap `LLM_MODEL` to any supported GitHub Model (e.g. `gpt-4.1`, `gpt-4.1-nano`, etc.).
* New Relic variables are no longer required unless you re‑enable telemetry instrumentation.

Optional variables:
* `OPENWEATHER_API_KEY` – enables the `get_weather` tool.
* `LOG_LEVEL` – adjust logging verbosity (`DEBUG`, `INFO`, etc.).
* `TOOL_HOSTNAME` / `TOOL_PORT` – override default tool server location.
* `NEW_RELIC_ENABLED` – set to `1` to enable instrumentation if `newrelic.ini` is present.

### Endpoints

Server (FastAPI):
* `GET /health` – simple liveness check.
* `POST /chat` – body `{ "message": "..." }`; returns final assistant response plus a `request_id` and duration.

### Execution

Using `uv` scripts:
* `uv run mcp-test-tools` – start tools MCP SSE server.
* `uv run mcp-test-server` – start FastAPI chat server.
* `uv run mcp-test-client` – (if present) start Streamlit client.
* `uv run run-all` – start tools + server (+ client if available) in one process manager.

### Logging

Structured logs include correlation IDs (`request_id`) and timing metrics.
Avoid using `message` in logging `extra`; we prefix with `user_message` instead.
All logs go to stdout; you can pipe or collect with a log forwarder.

### Security Notes

* The `read_file` tool restricts access to the `data/` directory only.
* Do not commit real API keys. Use `.env` files excluded from VCS.
* Weather tool has a short timeout (5s) and error handling for network failures.

### Extending

Add new tools by decorating functions with `@mcp.tool("name")` in `tools/tools_server.py`.
The agent in `server/agent.py` automatically loads them if you include adapter initialization.


### Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `FileNotFoundError: ../newrelic.ini` | Running from a different CWD | Use provided conditional init (NEW_RELIC_ENABLED) or move `newrelic.ini` to project root. |
| 401 / model errors | Bad or missing `OPENAI_API_KEY` | Regenerate PAT with `models.read` scope; re-export env. |
| Weather tool returns configuration error | Missing `OPENWEATHER_API_KEY` | Add key to both `tools/.env` and `server/.env` if agent reasoning uses it. |
| High latency | Cold model/client instantiation each request | Consider caching the `OpenAIChatCompletionClient` in `app.state`. |
| Division by zero error | User asked invalid operation | Calculator tool intentionally returns error string; agent should handle. |

### Next Ideas
* Agent-to-agent transcript endpoint (multi-agent chat) for richer demos.
* Azure resource tools integration via MCP for cloud state inspection.
* Structured JSON logging (replace format string with a custom formatter).
