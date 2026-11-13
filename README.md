# MCP-Based Data Analytics AI Agent

Upload a CSV or XLSX file, then ask questions in plain English. An AI agent picks the right tools:
- **Pandas MCP** – exact calculations (counts, averages, group-by, filters).
- **RAG MCP** – finds rows or text that match a question by meaning.
- **Web Search MCP** – optional outside information (needs a remote MCP URL).

## Architecture

```
Browser -> Flask (app.py)
              |
        LangChain agent (agent/ai_agent.py)
              |  Streamable HTTP
        MCP Aggregator (aggregator/aggregator_server.py)  http://127.0.0.1:8000/mcp
              |-- Pandas MCP  (loaded inside the aggregator, pandas_mcp/pandas_server.py)
              |-- RAG MCP     (loaded inside the aggregator, rag_mcp/rag_server.py)
              |-- Web Search  (remote URL, optional)
```

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install the packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Open `.env` and fill in `OPENROUTER_API_KEY` (from https://openrouter.ai/keys). `MODEL` is optional (default `openai/gpt-4o-mini`, a ChatGPT model). Also set `SECRET_KEY` (it signs the session cookie that separates users).
   Web search is optional: leave `WEB_SEARCH_MCP_URL` empty to skip it.

## Running

Open two terminals in the project folder (with the virtual environment active).

Terminal 1 – start the aggregator first:
```bash
python -m aggregator.aggregator_server
```

Terminal 2 – start the web app:
```bash
python app.py
```

Then open http://127.0.0.1:5000, attach a file with the **+** button (it uploads at once) and ask a question.

## Testing

Check the pandas functions (no internet or API key needed):
```bash
python tests/test_analytics.py
```

Example questions to try with `data/train.csv`:
- How many rows are in the dataset?
- What is the average value of each column?
- Calculate the average of `fare` for each `pclass`.
- Filter rows where `age` is greater than 50.
- How many passengers survived? Calculate the survival rate by `sex`.

Example questions for `data/ProjectPlan.xlsx`:
- How many tasks are assigned to each developer?
- Which tasks have no assignment?

## Outside-the-dataset toggle

By default the agent only answers questions about your dataset. Tick **Allow questions outside the dataset** in the message box to let it answer general questions too. The wording of both modes is in `config/prompts.py`.

## Supported files

- `.csv` and `.xlsx`, up to 10 MB (change `MAX_UPLOAD_MB` in `config/settings.py`).

## Tool list (what the agent can call)

| Tool (prefixed by the aggregator) | Purpose |
|---|---|
| `pandas_get_dataset_info` | Rows, columns, data types, empty cells |
| `pandas_get_column_summary` | Statistics for one column |
| `pandas_aggregate_data` | count, sum, mean, min or max of a column |
| `pandas_groupby_data` | Calculate a value per group |
| `pandas_filter_dataset` | Filter rows with `==`, `!=`, `>`, `<`, `>=`, `<=`, `isnull`, `notnull` |
| `rag_load_dataset` / `rag_search_dataset` / `rag_get_dataset_info` | Index and search rows by meaning |
| `web_search_*` | Only when `WEB_SEARCH_MCP_URL` is set |

Every `pandas_*` and `rag_*` tool takes a `dataset_id` argument (the session id). The app fills it in automatically on every tool call (`agent/ai_agent.py`), so the AI model cannot forget it or use another user's id.

## Project layout and the guide

Differences from the PDF's folder tree, on purpose, to keep the code small:
- `config/prompts.py` holds the LLM prompt; `static/` holds the CSS and JS.
- The RAG embedding and FAISS code live together in `rag_mcp/rag_server.py` (no `embeddings.py` / `vector_store.py`).
- The agent talks to the aggregator inside `agent/ai_agent.py` (no `mcp_client.py`).
- There is no `web_search_mcp/` folder: the web search MCP is a remote service (Tavily), set with `WEB_SEARCH_MCP_URL`.

## Environment variables

See `.env.example`. Never commit the real `.env` file.

## Limits

- Each browser session has its own dataset (`uploads/<session id>/`, one file at a time). Session folders older than 24 hours are deleted on the next upload (`KEEP_HOURS` in `app.py`).
- The RAG index is kept in memory, so it is rebuilt after the aggregator restarts.
- The web search server URL and authentication depend on the provider. Check the provider's documentation before setting `WEB_SEARCH_MCP_URL`.
- Do not expose the development servers to the internet.
