"""
LangChain AI agent.

What it does for one question:
  1. Connects to the aggregator and asks it "which tools do you have?"
  2. Gives those tools to the LLM (through OpenRouter).
  3. The LLM picks a tool, the tool runs, the LLM reads the result and writes the answer.
  4. It repeats step 3 until the LLM has enough information.
"""
import httpx
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config.prompts import SCOPE_ANYTHING, SCOPE_DATASET_ONLY, SYSTEM_PROMPT
from config.settings import AGGREGATOR_URL, MODEL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL


MAX_ATTEMPTS = 1  # 1 = no retry (retries burn the free-model rate limit); raise it to retry


class AgentError(Exception):
    """An error whose message is safe and clear enough to show to the user."""


async def ask_agent(question, dataset_id, allow_outside=False):
    """Send one question to the agent and return its text answer.
    allow_outside=True lets it answer questions that are not about the dataset."""
    if not OPENROUTER_API_KEY:
        raise AgentError("OPENROUTER_API_KEY is empty. Add it to the .env file and restart the app.")

    # Fill in dataset_id ourselves on every tool call. A weak model may forget it or
    # guess a wrong one; this way it can never be missing or point to another user's data.
    async def add_dataset_id(request, handler):
        if request.name.startswith(("pandas_", "rag_")):  # web search tools take no dataset_id
            request = request.override(args={**request.args, "dataset_id": dataset_id})
        return await handler(request)

    # Connect to the aggregator, which lists all the tools it can use.
    client = MultiServerMCPClient(
        {"aggregator": {"transport": "streamable_http", "url": AGGREGATOR_URL}},
        tool_interceptors=[add_dataset_id],
    )
    try:
        tools = await client.get_tools()
    except Exception as exc:
        raise AgentError(
            f"Cannot reach the MCP aggregator at {AGGREGATOR_URL}. "
            f"Start it with: python -m aggregator.aggregator_server ({type(exc).__name__})"
        ) from exc

    # The LLM, reached through OpenRouter. temperature=0 keeps answers consistent.
    # Own HTTP client per request: each request runs in a new event loop (asyncio.run in app.py),
    # and a client shared between loops fails with "Event loop is closed" on the second question.
    async with httpx.AsyncClient(timeout=30) as http:  # give up on a stuck model call after 30s
        llm = ChatOpenAI(
            model=MODEL,
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
            temperature=0,
            http_async_client=http,
        )

        # create_react_agent runs the "LLM picks tool -> run tool -> LLM answers" loop.
        scope = SCOPE_ANYTHING if allow_outside else SCOPE_DATASET_ONLY
        agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT.format(dataset_id=dataset_id, scope=scope))
        # A model call can fail once (network blip, busy server) and work on the next try, so retry a few times.
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                result = await agent.ainvoke({"messages": [("user", question)]})
                return str(result["messages"][-1].content)
            except Exception as exc:
                if attempt < MAX_ATTEMPTS:
                    continue
                # Most often: wrong or expired OpenRouter key, no credit, or the model is busy.
                raise AgentError(
                    f"The AI model request failed ({type(exc).__name__}: {exc}). "
                    "Check OPENROUTER_API_KEY (and credit) and MODEL in .env, then try again."
                ) from exc
