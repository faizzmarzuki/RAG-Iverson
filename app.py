"""
Flask web app: upload a CSV/XLSX file, then ask questions in plain English.

Run it (after the aggregator is running):
    python app.py
Then open http://127.0.0.1:5000
"""
import asyncio
import shutil
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session
from werkzeug.utils import secure_filename

from agent.ai_agent import AgentError, ask_agent
from config.settings import (
    ALLOWED_EXTENSIONS,
    FLASK_DEBUG,
    FLASK_HOST,
    FLASK_PORT,
    MAX_UPLOAD_MB,
    SECRET_KEY,
    UPLOAD_FOLDER,
)
from pandas_mcp.analytics import get_dataset_info, load_dataset

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024  # refuse files that are too big
UPLOAD_FOLDER.mkdir(exist_ok=True)
KEEP_HOURS = 24  # session folders untouched for this long are deleted


def delete_old_folders():
    """Remove old session folders so uploads/ does not grow forever."""
    limit = time.time() - KEEP_HOURS * 3600
    for folder in UPLOAD_FOLDER.iterdir():
        if folder.is_dir() and folder.stat().st_mtime < limit:
            shutil.rmtree(folder, ignore_errors=True)


def user_folder():
    """Each browser session gets its own id and its own upload folder, so users do not mix data."""
    if "id" not in session:
        session["id"] = uuid.uuid4().hex
    return session["id"], UPLOAD_FOLDER / session["id"]


@app.errorhandler(413)
def too_big(_error):
    # Flask raises this when the file is over MAX_CONTENT_LENGTH. Send JSON so the page can show it.
    return jsonify(error=f"File is too big. The maximum size is {MAX_UPLOAD_MB} MB."), 413


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(error="No file uploaded"), 400

    filename = secure_filename(file.filename)  # removes unsafe characters from the name
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        return jsonify(error="Only CSV or XLSX files are supported"), 400

    delete_old_folders()  # runs before this user's folder is (re)created, so theirs is never old
    _, folder = user_folder()
    folder.mkdir(exist_ok=True)
    path = folder / filename
    file.save(path)

    # Check that pandas can really read the file before we accept it.
    try:
        info = get_dataset_info(load_dataset(path))
    except Exception as exc:
        path.unlink(missing_ok=True)
        return jsonify(error=f"Could not read the file: {exc}"), 400

    # Keep only this newest file, so the folder always holds the user's one active dataset.
    for old in folder.iterdir():
        if old != path:
            old.unlink()

    return jsonify(
        message="File uploaded successfully",
        file=filename,
        rows=info["rows"],
        columns=info["columns"],
    )


@app.route("/ask", methods=["POST"])
def ask():
    body = request.get_json(silent=True) or {}
    question = body.get("query", "").strip()
    allow_outside = body.get("allow_outside") is True  # the page's toggle; anything else means off
    if not question:
        return jsonify(error="Question cannot be empty"), 400
    dataset_id, folder = user_folder()
    if not folder.exists() or not any(folder.iterdir()):
        return jsonify(error="Upload a dataset first"), 400
    folder.touch()  # asking counts as activity, so an active user's folder is not deleted

    try:
        # The agent code is async, so asyncio.run lets this normal Flask route call it.
        answer = asyncio.run(ask_agent(question, dataset_id, allow_outside))
    except AgentError as exc:
        return jsonify(error=str(exc)), 502  # a clear, user-friendly message
    except Exception as exc:
        return jsonify(error=f"Unexpected error: {type(exc).__name__}"), 500

    return jsonify(question=question, answer=answer)


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
