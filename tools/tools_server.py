from dotenv import load_dotenv
from util.llm_utils import query_llm
import click
import os
from mcp.server.fastmcp import FastMCP, Context
import sys
from pathlib import Path
import requests
import logging
import uuid
import time
from random import choice, uniform
import newrelic.agent

sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables from .env file
load_dotenv()

mcp = FastMCP("Tools service")
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | tools | %(message)s",
    )
logger = logging.getLogger("tools")
logger.debug("Tools MCP server initializing")


def get_openai_base_url() -> str:
    return os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1/")


@mcp.tool("calculator")
def calculator(a: int, b: int, operation: str, ctx: Context) -> str:
    """Perform basic arithmetic operations.

    Args:
        a: First number
        b: Second number
        operation: Operation to perform (add, subtract, multiply, divide)

    Returns:
        Result of the operation as a string
    """
    request_id = str(uuid.uuid4())
    t0 = time.time()
    logger.debug("[calculator] start", extra={
                 "request_id": request_id, "a": a, "b": b, "operation": operation})
    operations = {
        "add": a + b,
        "subtract": a - b,
        "multiply": a * b,
        "divide": a / b if b != 0 else "Error: Division by zero",
    }
    result = operations.get(operation.lower(), "Error: Invalid operation")
    newrelic.agent.add_custom_attribute("operation", operation)
    newrelic.agent.add_custom_attribute("operand_a", a)
    newrelic.agent.add_custom_attribute("operand_b", b)
    elapsed_ms = int((time.time() - t0) * 1000)
    logger.info(
        "[calculator] complete",
        extra={"request_id": request_id, "a": a, "b": b,
               "operation": operation, "result": result, "elapsed_ms": elapsed_ms},
    )
    return str(result)


# 🌏 Predefined Destinations with Descriptions
DESTINATIONS = {
    "Garmisch-Partenkirchen, Germany": "🏔️ Alpine village with stunning mountain views",
    "Munich, Germany": "🍺 Bavarian capital famous for culture and beer",
    "Berlin, Germany": "🎨 Historic and vibrant cultural hub",
    "Rome, Italy": "🏛️ Ancient city with rich history and art",
    "Barcelona, Spain": "🏖️ Coastal city with stunning architecture",
    "Boston, USA": "🍀 Historic city with rich colonial heritage",
    "New York, USA": "🗽 The city that never sleeps",
    "Tokyo, Japan": "🗾 Bustling metropolis with ancient temples",
    "Sydney, Australia": "🦘 Opera House and beautiful beaches",
    "Cairo, Egypt": "🔺 Gateway to ancient wonders",
    "Cape Town, South Africa": "🌅 Scenic beauty and Table Mountain",
    "Rio de Janeiro, Brazil": "🎭 Vibrant culture and beaches",
    "Bali, Indonesia": "🌴 Tropical paradise and spiritual haven",
    "Paris, France": "🗼 The City of Light, romantic and iconic"
}


@mcp.tool("get_random_destination")
def get_random_destination() -> str:
    """Get a random vacation destination.

    Returns:
        str: A randomly selected destination from our predefined list
    """

    # Simulate network latency with a small random sleep
    delay_seconds = uniform(0, 0.99)
    time.sleep(delay_seconds)

    # Return a random destination from the list
    # Get and remove a random destination
    chc = choice(list(DESTINATIONS.keys()))
    destination = chc + \
        ": " + DESTINATIONS[chc]
    logger.info("[get_destination_from_list] selected",
                extra={"destination": destination})
    newrelic.agent.add_custom_attribute("selected_destination", destination)
    return destination


@mcp.tool("get_weather")
def get_weather(city: str, ctx: Context) -> str:
    """Get current weather information for a city.

    Args:
        city: Name of the city (e.g., 'London', 'New York')

    Returns:
        Weather information as a string
    """
    request_id = str(uuid.uuid4())
    t0 = time.time()
    logger.debug("[get_weather] start", extra={
                 "request_id": request_id, "city": city})
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        logger.warning("[get_weather] missing API key",
                       extra={"request_id": request_id})
        return "Weather service not configured. Please set OPENWEATHER_API_KEY environment variable."
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        weather = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        result = f"Weather in {city}: {weather}, Temperature: {temp}°C (feels like {feels_like}°C), Humidity: {humidity}%"
        elapsed_ms = int((time.time() - t0) * 1000)
        logger.info(
            "[get_weather] complete",
            extra={"request_id": request_id, "city": city,
                   "weather": weather, "temp": temp, "elapsed_ms": elapsed_ms},
        )
        newrelic.agent.add_custom_attribute("weather_info", result)
        return result
    except requests.exceptions.RequestException as e:
        logger.error("[get_weather] request_error", extra={
                     "request_id": request_id, "city": city, "error": str(e)})
        return f"Error fetching weather data for {city}. Please check the city name."
    except KeyError as e:
        logger.error("[get_weather] parse_error", extra={
                     "request_id": request_id, "city": city, "error": str(e)})
        return f"Error parsing weather data for {city}."


@mcp.tool("read_file")
def read_file(filename: str, ctx: Context) -> str:
    """Read contents of a file from the data directory.

    Args:
        filename: Name of the file to read (must be in the 'data' directory)

    Returns:
        Contents of the file as a string
    """
    request_id = str(uuid.uuid4())
    t0 = time.time()
    logger.debug("[read_file] start", extra={
                 "request_id": request_id, "filename": filename})
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    file_path = data_dir / filename
    try:
        file_path = file_path.resolve()
        newrelic.agent.add_custom_attribute("file_path", str(file_path))
        if not str(file_path).startswith(str(data_dir.resolve())):
            logger.warning("[read_file] path_outside_data_dir", extra={
                           "request_id": request_id, "filename": filename})
            return "Error: Access denied. File must be in the data directory."
        if not file_path.exists():
            logger.info("[read_file] not_found", extra={
                        "request_id": request_id, "filename": filename})
            return f"Error: File '{filename}' not found in data directory."
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        elapsed_ms = int((time.time() - t0) * 1000)
        logger.info(
            "[read_file] complete",
            extra={"request_id": request_id, "filename": filename,
                   "size": len(content), "elapsed_ms": elapsed_ms},
        )
        return content
    except Exception as e:
        logger.error("[read_file] error", extra={
                     "request_id": request_id, "filename": filename, "error": str(e)})
        return f"Error reading file '{filename}': {str(e)}"


@click.command()
@click.option("--port", default=8090, help="Port to listen on for SSE")
def main(port: int):

    # Initialize New Relic Python Agent
    newrelic.agent.initialize("newrelic.ini")
    newrelic.agent.register_application(timeout=10)
    """Run the FastMCP server."""
    logger.info("[startup] tools server starting", extra={"port": port})
    mcp.settings.port = port
    t0 = time.time()
    mcp.run('sse')
    logger.info("[shutdown] tools server stopped", extra={
                "elapsed_ms": int((time.time() - t0) * 1000)})


if __name__ == "__main__":

    # Initialize New Relic Python Agent
    # newrelic.agent.initialize("../newrelic.ini")
    # newrelic.agent.register_application(timeout=10)

    main()
