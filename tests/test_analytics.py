"""
Small self-checks for pandas_mcp/analytics.py.

Run from the project folder:
    python tests/test_analytics.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from pandas_mcp import analytics as a


def sample():
    return pd.DataFrame({
        "name": ["A", "B", "C", "D"],
        "pclass": [1, 1, 3, 3],
        "fare": [100.0, 50.0, 10.0, None],
        "survived": [1, 0, 1, 0],
    })


def test_dataset_info():
    info = a.get_dataset_info(sample())
    assert info["rows"] == 4
    assert info["missing_values"]["fare"] == 1


def test_mean_skips_empty_cells():
    result = a.aggregate_data(sample(), "fare", "mean")["result"]
    assert abs(result - 160 / 3) < 1e-9  # (100 + 50 + 10) / 3


def test_groupby_mean():
    groups = a.groupby_data(sample(), ["pclass"], "fare", "mean")["groups"]
    by_class = {g["pclass"]: g["fare"] for g in groups}
    assert by_class[1] == 75.0
    assert by_class[3] == 10.0


def test_filter_numeric_text_value():
    result = a.filter_dataset(sample(), "fare", ">", "40")  # "40" is turned into a number
    assert result["total_matches"] == 2


def test_filter_isnull():
    result = a.filter_dataset(sample(), "fare", "isnull")
    assert result["total_matches"] == 1
    assert result["rows"][0]["name"] == "D"


def test_unknown_column_is_rejected():
    try:
        a.aggregate_data(sample(), "salary", "sum")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown column")


def test_bad_function_is_rejected():
    try:
        a.aggregate_data(sample(), "fare", "eval")
    except ValueError:
        return
    raise AssertionError("expected ValueError for bad function")


def test_dataset_id_cannot_escape_uploads_folder():
    for bad_id in ["../x", "..", "a/b", ""]:
        try:
            a.active_dataset_path(bad_id)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for dataset_id {bad_id!r}")


def test_users_only_see_their_own_file():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        a.UPLOAD_FOLDER = Path(tmp)  # point the module at a throwaway folder
        (Path(tmp) / "user1").mkdir()
        (Path(tmp) / "user1" / "data.csv").write_text("x\n1\n")
        assert a.active_dataset_path("user1").name == "data.csv"
        try:
            a.active_dataset_path("user2")  # user2 uploaded nothing
        except ValueError:
            return
        raise AssertionError("user2 must not see user1's data")


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
            print("passed:", name)
    print("All tests passed.")
