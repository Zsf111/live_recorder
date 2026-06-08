import os
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, send_file, abort

import psycopg2

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())
_web_pw = os.environ.get("WEB_PASSWORD") or os.environ.get("DB_PASSWORD")
if not _web_pw:
    raise RuntimeError("WEB_PASSWORD or DB_PASSWORD must be set")
WEB_PASSWORD = _web_pw

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "downloads")


def _connect():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        database=os.environ.get("DB_NAME", "live_recorder"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ["DB_PASSWORD"],
    )


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == WEB_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        error = "密码错误"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT room_id, streamer_name, platform, current_status, is_monitored FROM t_streamer_config ORDER BY platform, streamer_name")
    streamers = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("dashboard.html", streamers=streamers)


@app.route("/streamers", methods=["GET"])
@login_required
def streamers_page():
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT room_id, streamer_name, platform, is_monitored, current_status FROM t_streamer_config ORDER BY platform, streamer_name")
    streamers = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("streamers.html", streamers=streamers)


@app.route("/api/streamers/add", methods=["POST"])
@login_required
def api_add_streamer():
    room_id = request.form.get("room_id", "").strip()
    name = request.form.get("name", "").strip()
    platform = request.form.get("platform", "").strip()

    if not room_id or not name or platform not in ("bilibili", "twitch"):
        return "参数错误", 400

    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO t_streamer_config (room_id, streamer_name, platform) VALUES (%s, %s, %s) ON CONFLICT (room_id) DO NOTHING",
        (room_id, name, platform),
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("streamers_page"))


@app.route("/api/streamers/edit", methods=["POST"])
@login_required
def api_edit_streamer():
    room_id = request.form.get("room_id", "").strip()
    name = request.form.get("name", "").strip()
    monitor = request.form.get("monitor")

    if not room_id:
        return "缺少 room_id", 400

    conn = _connect()
    cur = conn.cursor()
    if name:
        cur.execute("UPDATE t_streamer_config SET streamer_name = %s WHERE room_id = %s", (name, room_id))
    if monitor is not None:
        cur.execute("UPDATE t_streamer_config SET is_monitored = %s WHERE room_id = %s", (monitor == "1", room_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("streamers_page"))


@app.route("/api/streamers/delete", methods=["POST"])
@login_required
def api_delete_streamer():
    room_id = request.form.get("room_id", "").strip()
    if not room_id:
        return "缺少 room_id", 400
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM t_streamer_config WHERE room_id = %s", (room_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("streamers_page"))


@app.route("/recordings")
@login_required
def recordings_page():
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, room_id, start_time, end_time, file_path, status FROM t_record_log ORDER BY start_time DESC LIMIT 100"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    recordings = []
    for row in rows:
        r = dict(zip(["id", "room_id", "start_time", "end_time", "file_path", "status"], row))
        # Extract filename for display and relative path for download
        r["filename"] = os.path.basename(r["file_path"] or "")
        r["completed"] = r["status"] == "SUCCESS" and r["file_path"] and os.path.exists(r["file_path"])
        recordings.append(r)

    return render_template("recordings.html", recordings=recordings)


@app.route("/download/<path:subpath>")
@login_required
def download_file(subpath):
    # Security: prevent directory traversal
    safe = os.path.normpath(subpath).lstrip("/")
    file_path = os.path.join(DOWNLOAD_DIR, safe)
    real_download = os.path.realpath(DOWNLOAD_DIR)
    real_file = os.path.realpath(file_path)
    if not real_file.startswith(real_download):
        abort(403)
    if not os.path.isfile(file_path):
        abort(404)
    return send_file(file_path, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
