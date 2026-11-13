"""
Central settings for the whole project.

Every value comes from the .env file, so secrets never live in the code.
Other files import what they need from here, e.g.:
    from config.settings import OPENROUTER_API_KEY
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# The project root folder (the folder that contains app.py).
# Using absolute paths means the code works no matter where you start it from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Read the .env file that sits next to app.py.
load_dotenv(PROJECT_ROOT / ".env")

# ---------- LLM (OpenRouter) ----------
# OpenRouter can call ChatGPT models (and your own OpenAI key, if you add it in OpenRouter's settings).
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.getenv("MODEL") or "openai/gpt-4o-mini"  # a ChatGPT model, good at tool use

# ---------- Web Search MCP (optional) ----------
# Leave WEB_SEARCH_MCP_URL empty to run without web search.
WEB_SEARCH_MCP_URL = os.getenv("WEB_SEARCH_MCP_URL", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ---------- MCP Aggregator ----------
AGGREGATOR_HOST = os.getenv("AGGREGATOR_HOST", "127.0.0.1")
AGGREGATOR_PORT = int(os.getenv("AGGREGATOR_PORT", "8000"))
# The agent connects to this address. It must match the aggregator's host and port.
AGGREGATOR_URL = f"http://{AGGREGATOR_HOST}:{AGGREGATOR_PORT}/mcp"

# ---------- Flask ----------
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
# Signs the session cookie. If .env has none, use a random one (users get a new session after each restart).
SECRET_KEY = os.getenv("SECRET_KEY") or os.urandom(16).hex()

# ---------- RAG ----------
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# ---------- Uploads ----------
UPLOAD_FOLDER = PROJECT_ROOT / "uploads"
# Each user's file is saved in uploads/<session id>/, so users never see each other's data.
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
MAX_UPLOAD_MB = 10
