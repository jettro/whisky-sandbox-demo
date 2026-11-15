import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path(os.getenv("DEMO_OUTPUT_DIR", "output"))


def get_model() -> str:
    model = os.getenv("DEMO_MODEL")
    if not model:
        raise RuntimeError("Set DEMO_MODEL in your .env file.")
    return model


def get_agent_model() -> str:
    """DEMO_MODEL as a Pydantic AI model string; a bare name is treated as an OpenAI model."""
    model = get_model()
    return model if ":" in model else f"openai:{model}"


def require_openai_key() -> None:
    """Fail early with a clear message. Only checks presence; the value is never printed."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY in your .env file (see .env.example).")


def configure_logfire() -> bool:
    """Turn on Logfire tracing only when a token is configured; otherwise do nothing.

    Returns whether tracing is enabled. Running without a Logfire account always works.
    """
    if not os.getenv("LOGFIRE_TOKEN"):
        return False
    import logfire

    logfire.configure(service_name="whisky-sandbox-demo", send_to_logfire="if-token-present")
    logfire.instrument_pydantic_ai()
    return True
