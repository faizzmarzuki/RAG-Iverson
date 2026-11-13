"""
Pandas MCP server.

It runs as a separate program (STDIO transport). The aggregator starts it for you,
so you normally do NOT run this file yourself.
Each @mcp.tool() function below becomes a tool the AI agent can call.
Every tool needs dataset_id: it tells the tool which user's uploaded file to use.
"""
import sys
from pathlib import Path

# Add the project root to Python's search path so "config" and "pandas_mcp" can be imported.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP

from pandas_mcp import analytics

mcp = FastMCP("pandas-analytics")


@mcp.tool()
def get_dataset_info(dataset_id: str) -> dict:
    """Return the number of rows, column names, data types and empty cells of the uploaded dataset."""
    return analytics.get_dataset_info(analytics.load_active_dataset(dataset_id))


@mcp.tool()
def get_column_summary(dataset_id: str, column: str) -> dict:
    """Return descriptive statistics (count, mean, min, max, ...) for one column."""
    return analytics.get_column_summary(analytics.load_active_dataset(dataset_id), column)


@mcp.tool()
def aggregate_data(dataset_id: str, column: str, function: str) -> dict:
    """Calculate one value for a column. function must be: count, sum, mean, min or max."""
    return analytics.aggregate_data(analytics.load_active_dataset(dataset_id), column, function)


@mcp.tool()
def groupby_data(dataset_id: str, group_by: list[str], value_column: str, function: str) -> dict:
    """Group rows by columns, e.g. group_by=['pclass'], then calculate count, sum, mean, min or max of value_column."""
    return analytics.groupby_data(analytics.load_active_dataset(dataset_id), group_by, value_column, function)


@mcp.tool()
def filter_dataset(dataset_id: str, column: str, operator: str, value: str = "") -> dict:
    """Filter rows. operator must be one of: ==, !=, >, <, >=, <=, isnull, notnull. value is not needed for isnull/notnull."""
    return analytics.filter_dataset(analytics.load_active_dataset(dataset_id), column, operator, value)


if __name__ == "__main__":
    mcp.run()  # default transport is STDIO
