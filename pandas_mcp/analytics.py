"""
Plain pandas functions for the data analysis.

This file has NO MCP code, so you can test it on its own.
pandas_server.py wraps these functions as MCP tools.
"""
import operator
from pathlib import Path

import pandas as pd

from config.settings import UPLOAD_FOLDER

ALLOWED_AGGREGATIONS = {"count", "sum", "mean", "min", "max"}
# Maps the text the LLM sends to a real Python comparison function.
# We never run text as code, which keeps the tool safe.
ALLOWED_OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "isnull": None,   # special case: keep rows where the column is empty
    "notnull": None,  # special case: keep rows where the column has a value
}
MAX_ROWS_RETURNED = 20


def tidy_excel(raw):
    """Turn a report-style sheet (title block, blank columns, header lower down) into a normal table.

    shortcut: the header is the fuller row among the first 30 rows; only the first sheet is read.
    """
    header_row = raw.head(30).notna().sum(axis=1).idxmax()  # the title rows have few cells, the header row many
    table = raw.iloc[header_row + 1:].dropna(how="all").dropna(axis=1, how="all")
    names = raw.iloc[header_row][table.columns]
    table.columns = [
        " ".join(str(name).split()) if pd.notna(name) else f"column_{n}"  # one-line names, blank ones numbered
        for n, name in zip(table.columns, names)
    ]
    return table.reset_index(drop=True).infer_objects()  # numbers read as text become real numbers


def load_dataset(path):
    """Read a CSV or XLSX file into a DataFrame (a table in memory)."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".xlsx":
        return tidy_excel(pd.read_excel(path, header=None))
    raise ValueError("Only .csv and .xlsx files are supported")


def active_dataset_path(dataset_id):
    """Return the file uploaded by one user. Each user (browser session) has an own folder: uploads/<dataset_id>/."""
    # Only letters and digits are allowed, so the id can never point outside the uploads folder.
    if not dataset_id.isalnum():
        raise ValueError("Invalid dataset_id")
    files = sorted((UPLOAD_FOLDER / dataset_id).glob("*"))
    if not files:
        raise ValueError("No dataset uploaded yet. Upload a CSV or XLSX file first.")
    return files[0]


def load_active_dataset(dataset_id):
    """Read the dataset of one user."""
    return load_dataset(active_dataset_path(dataset_id))


def _native(value):
    """Turn numpy/pandas values into plain Python values that JSON can store."""
    if pd.isna(value):
        return None  # empty cell -> None (JSON null)
    if hasattr(value, "item"):
        return value.item()  # numpy number -> normal Python number
    return value


def _check_columns(df, columns):
    """Stop early with a clear message if a column name does not exist."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Unknown column(s) {missing}. Available columns: {list(df.columns)}")


def _check_aggregation(func):
    if func not in ALLOWED_AGGREGATIONS:
        raise ValueError(f"Function must be one of {sorted(ALLOWED_AGGREGATIONS)}")


def _rows_as_json(df):
    """Convert a DataFrame to a list of dicts with plain values."""
    return [{col: _native(val) for col, val in row.items()} for row in df.to_dict("records")]


def get_dataset_info(df):
    """Row count, column names, data types and number of empty cells per column."""
    return {
        "rows": len(df),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": {col: int(n) for col, n in df.isna().sum().items()},
    }


def get_column_summary(df, column):
    """Descriptive statistics for one column (count, mean, min, max, ...)."""
    _check_columns(df, [column])
    summary = df[column].describe()  # empty cells are skipped automatically
    return {
        "column": column,
        "missing": int(df[column].isna().sum()),
        "summary": {name: _native(val) for name, val in summary.items()},
    }


def aggregate_data(df, column, func):
    """One number for a whole column: count, sum, mean, min or max."""
    _check_columns(df, [column])
    _check_aggregation(func)
    try:
        result = getattr(df[column], func)()  # empty cells are skipped
    except TypeError:
        raise ValueError(f"'{func}' needs a numeric column, but '{column}' is text")
    return {"column": column, "function": func, "result": _native(result)}


def groupby_data(df, group_by, value_column, func):
    """Group rows by one or more columns and calculate one value per group."""
    _check_columns(df, group_by + [value_column])
    _check_aggregation(func)
    try:
        grouped = df.groupby(group_by)[value_column].agg(func).reset_index()
    except TypeError:
        raise ValueError(f"'{func}' needs a numeric column, but '{value_column}' is text")
    return {
        "group_by": group_by,
        "value_column": value_column,
        "function": func,
        "groups": _rows_as_json(grouped),
    }


def filter_dataset(df, column, operator_name, value=None):
    """Keep only the rows that match a condition. Returns the count and the first rows."""
    _check_columns(df, [column])
    if operator_name not in ALLOWED_OPERATORS:
        raise ValueError(f"Operator must be one of {list(ALLOWED_OPERATORS)}")

    if operator_name == "isnull":
        mask = df[column].isna()
    elif operator_name == "notnull":
        mask = df[column].notna()
    else:
        # Numbers must be compared as numbers, so "50" becomes 50.0 for numeric columns.
        if pd.api.types.is_numeric_dtype(df[column]):
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"'{column}' is numeric, so the value must be a number")
        try:
            mask = ALLOWED_OPERATORS[operator_name](df[column], value)
        except TypeError:
            raise ValueError(f"Cannot compare '{column}' with '{operator_name}' using that value")

    matches = df[mask]
    return {
        "total_matches": int(len(matches)),
        "shown": min(len(matches), MAX_ROWS_RETURNED),
        "rows": _rows_as_json(matches.head(MAX_ROWS_RETURNED)),
    }
