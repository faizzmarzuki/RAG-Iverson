"""
MCP Aggregator.

One program that:
  1. loads the Pandas and RAG servers inside itself (fast, no sub-programs),
  2. connects to the Web Search server over the internet (if you set WEB_SEARCH_MCP_URL),
  3. shows ALL their tools on one address: http://127.0.0.1:8000/mcp

Start it first, in its own terminal:
    python -m aggregator.aggregator_server
"""
import sys
from pathlib import Path

# Add the project root to Python's search path so "config" can be imported.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server import create_proxy

from config.settings import (
    AGGREGATOR_HOST,
    AGGREGATOR_PORT,
    TAVILY_API_KEY,
    WEB_SEARCH_MCP_URL,
)
from pandas_mcp.pandas_server import mcp as pandas_mcp
from rag_mcp.rag_server import mcp as rag_mcp

aggregator = FastMCP("aggregator")

# Local servers are loaded INSIDE this program ("mounted"), so they start once.
# (Starting them as STDIO sub-programs on every request took 30-45 seconds each time.)
# The pandas tools get the prefix "pandas_". The rag tools already start with "rag_".
aggregator.mount(pandas_mcp, namespace="pandas")
aggregator.mount(rag_mcp)

# Remote server: only added when a URL is configured in .env. Its tools get the prefix "web_search_".
if WEB_SEARCH_MCP_URL:
    headers = {"Authorization": f"Bearer {TAVILY_API_KEY}"} if TAVILY_API_KEY else {}
    web_search = create_proxy(StreamableHttpTransport(WEB_SEARCH_MCP_URL, headers=headers), name="web_search")
    aggregator.mount(web_search, namespace="web_search")


if __name__ == "__main__":
    print(f"Aggregator running at http://{AGGREGATOR_HOST}:{AGGREGATOR_PORT}/mcp")
    aggregator.run(transport="http", host=AGGREGATOR_HOST, port=AGGREGATOR_PORT)
