import os
import re
import json
import shutil
import uuid
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory

from analysis.detector import GameDetector
from analysis.ai_analyzer import GrokVisionAnalyzer
from analysis.game_profiles import get_all_games
from clip_manager import ClipManager

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24).hex()
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 * 1024  # 10 GB for VOD uploads

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIPS_DIR = os.path.join(BASE_DIR, "static", "clips")
THUMBNAILS_DIR = os.path.join(BASE_DIR, "static", "thumbnails")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
LIBRARY_DIR = os.path.join(BASE_DIR, "library")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")

os.makedirs(CLIPS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(LIBRARY_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)

jobs = {}
clip_manager = ClipManager(CLIPS_DIR, THUMBNAILS_DIR, DOWNLOADS_DIR)


def _save_session(job_id):
    """Persist a completed job's state to disk."""
    job = jobs.get(job_id)
    if not job or job.get("status") != "complete":
        return
    session_data = {
        "job_id": job_id,
        "status": "complete",
        "clips": job["clips"],
        "vod_duration": job.get("vod_duration", 0),
        "vod_path": job.get("vod_path"),
        "url": job.get("url", ""),
        "message": job.get("message", ""),
        "created_at": job.get("created_at", datetime.now().isoformat()),
    }
    path = os.path.join(SESSIONS_DIR, f"{job_id}.json")
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(session_data, f, indent=2)
    os.replace(tmp_path, path)


def _load_sessions():
    """Load all saved session files into the jobs dict on startup."""
    for fname in os.listdir(SESSIONS_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(SESSIONS_DIR, fname)) as f:
                data = json.load(f)
            job_id = data["job_id"]
            # Filter out clips whose files no longer exist
            data["clips"] = [
                c for c in data.get("clips", [])
                if os.path.exists(os.path.join(CLIPS_DIR, c.get("filename", "")))
            ]
            jobs[job_id] = {
                "status": data["status"],
                "progress": 100,
                "message": data.get("message", "Restored session"),
                "clips": data["clips"],
                "error": None,
                "vod_path": data.get("vod_path"),
                "vod_duration": data.get("vod_duration", 0),
                "url": data.get("url", ""),
                "created_at": data.get("created_at", ""),
            }
        except (json.JSONDecodeError, KeyError, OSError):
            continue


_load_sessions()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/games")
def list_games():
    """Return list of supported games for the UI."""
    return jsonify({"games": get_all_games()})


@app.route("/api/analyze", methods=["POST"])
def start_analysis():
    data = request.get_json()
    url = data.get("url", "").strip()
    library_file = data.get("library_file", "").strip()
    api_key = data.get("api_key", "").strip()
    time_start = data.get("time_start", "").strip()
    time_end = data.get("time_end", "").strip()
    game_id = data.get("game", "arc_raiders").strip()

    # Option 1: Re-analyze a saved VOD from the library
    if library_file:
        safe_name = os.path.basename(library_file)
        lib_path = os.path.join(LIBRARY_DIR, safe_name)
        if not os.path.exists(lib_path):
            return jsonify({"error": "Saved VOD not found"}), 404

        job_id = str(uuid.uuid4())[:8]
        jobs[job_id] = {
            "status": "analyzing",
            "progress": 42,
            "message": "Loading saved VOD...",
            "clips": [],
            "error": None,
            "url": f"library:{safe_name}",
            "vod_path": lib_path,
            "vod_duration": 0,
        }

        thread = threading.Thread(
            target=_run_analysis_on_file, args=(job_id, lib_path, api_key, time_start, time_end, game_id), daemon=True
        )
        thread.start()
        return jsonify({"job_id": job_id})

    # Option 2: Download from URL
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    if not _is_valid_stream_url(url):
        return jsonify({"error": "Please provide a valid Twitch or YouTube VOD URL"}), 400

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "downloading",
        "progress": 5,
        "message": "Starting download...",
        "clips": [],
        "error": None,
        "url": url,
        "vod_path": None,
        "vod_duration": 0,
    }

    thread = threading.Thread(
        target=_run_analysis, args=(job_id, url, api_key, time_start, time_end, game_id), daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/library")
def list_library():
    """List all saved VODs in the library."""
    vods = []
    for f in sorted(os.listdir(LIBRARY_DIR)):
        fpath = os.path.join(LIBRARY_DIR, f)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            duration = clip_manager.get_vod_duration(fpath)
            vods.append({
                "filename": f,
                "size": size,
                "duration": duration,
            })
    return jsonify({"vods": vods})


@app.route("/api/library/<filename>/delete", methods=["POST"])
def delete_library_vod(filename):
    """Delete a saved VOD from the library."""
    safe_name = os.path.basename(filename)
    fpath = os.path.join(LIBRARY_DIR, safe_name)
    if os.path.exists(fpath):
        os.remove(fpath)
        return jsonify({"success": True})
    return jsonify({"error": "File not found"}), 404


@app.route("/api/sessions")
def list_sessions():
    """List all saved sessions for the Recent Sessions UI."""
    sessions = []
    for fname in sorted(os.listdir(SESSIONS_DIR), reverse=True):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(SESSIONS_DIR, fname)) as f:
                data = json.load(f)
            vod_available = bool(data.get("vod_path") and os.path.exists(data["vod_path"]))
            sessions.append({
                "job_id": data["job_id"],
                "clip_count": len(data.get("clips", [])),
                "url": data.get("url", ""),
                "created_at": data.get("created_at", ""),
                "vod_available": vod_available,
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return jsonify({"sessions": sessions})


@app.route("/api/sessions/<job_id>/delete", methods=["POST"])
def delete_session(job_id):
    """Delete a saved session."""
    safe_id = os.path.basename(job_id)
    path = os.path.join(SESSIONS_DIR, f"{safe_id}.json")
    if os.path.exists(path):
        os.remove(path)
        jobs.pop(job_id, None)
        return jsonify({"success": True})
    return jsonify({"error": "Session not found"}), 404


@app.route("/api/upload", methods=["POST"])
def upload_vod():
    """Accept a VOD file upload and start analysis."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    allowed_ext = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts", ".webm"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        return jsonify({"error": f"Unsupported file type. Use: {', '.join(allowed_ext)}"}), 400

    api_key = request.form.get("api_key", "").strip()
    time_start = request.form.get("time_start", "").strip()
    time_end = request.form.get("time_end", "").strip()
    game_id = request.form.get("game", "arc_raiders").strip()

    job_id = str(uuid.uuid4())[:8]

    # Save to library directly with original filename
    safe_name = re.sub(r'[^\w\-. ]', '_', file.filename)
    lib_path = os.path.join(LIBRARY_DIR, safe_name)
    file.save(lib_path)

    jobs[job_id] = {
        "status": "analyzing",
        "progress": 42,
        "message": "File saved! Analyzing...",
        "clips": [],
        "error": None,
        "url": f"upload:{safe_name}",
        "vod_path": lib_path,
        "vod_duration": 0,
    }

    thread = threading.Thread(
        target=_run_analysis_on_file,
        args=(job_id, lib_path, api_key, time_start, time_end, game_id),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/jobs/<job_id>")
def get_job(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    # Don't expose vod_path to frontend
    safe = {k: v for k, v in job.items() if k != "vod_path"}
    return jsonify(safe)


@app.route("/api/clips/<job_id>")
def get_clips(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"clips": job["clips"], "vod_duration": job.get("vod_duration", 0)})


@app.route("/api/clips/<job_id>/<clip_id>/download")
def download_clip(job_id, clip_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    for clip in job["clips"]:
        if clip["id"] == clip_id:
            return send_from_directory(
                CLIPS_DIR, clip["filename"],
                as_attachment=True,
                download_name=clip["filename"]
            )

    return jsonify({"error": "Clip not found"}), 404


@app.route("/api/clips/<job_id>/<clip_id>/trim", methods=["POST"])
def trim_clip(job_id, clip_id):
    """Re-extract a clip with new start/end times."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    vod_path = job.get("vod_path")
    if not vod_path or not os.path.exists(vod_path):
        return jsonify({"error": "VOD no longer available. Re-analyze to trim clips."}), 400

    data = request.get_json()
    new_start = data.get("start")
    new_end = data.get("end")

    if new_start is None or new_end is None:
        return jsonify({"error": "start and end required"}), 400

    new_start = max(0, float(new_start))
    new_end = float(new_end)

    if new_end <= new_start:
        return jsonify({"error": "End must be after start"}), 400

    # Find the clip to update
    for i, clip in enumerate(job["clips"]):
        if clip["id"] == clip_id:
            # Delete old clip file
            clip_manager.delete_clip(clip)

            # Re-extract with new times
            result = clip_manager.reclip(vod_path, job_id, clip_id, new_start, new_end)
            if not result:
                return jsonify({"error": "Failed to re-extract clip"}), 500

            # Update clip info
            clip["filename"] = result["filename"]
            clip["thumbnail"] = result["thumbnail"]
            clip["start_time"] = result["start_time"]
            clip["end_time"] = result["end_time"]
            clip["duration"] = result["duration"]
            clip["timestamp_display"] = result["timestamp_display"]

            _save_session(job_id)
            return jsonify({"success": True, "clip": clip})

    return jsonify({"error": "Clip not found"}), 404


@app.route("/api/clips/<job_id>/<clip_id>/tiktok", methods=["POST"])
def make_tiktok(job_id, clip_id):
    """Convert a clip to TikTok vertical format."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json()
    gameplay_region = data.get("gameplay")
    webcam_region = data.get("webcam")
    layout = data.get("layout", "stacked")

    if not gameplay_region:
        return jsonify({"error": "Gameplay region is required"}), 400

    for clip in job["clips"]:
        if clip["id"] == clip_id:
            clip_path = os.path.join(CLIPS_DIR, clip["filename"])
            if not os.path.exists(clip_path):
                return jsonify({"error": "Clip file not found"}), 404

            result = clip_manager.make_tiktok(
                clip_path, job_id, clip_id, gameplay_region, webcam_region, layout
            )
            if not result:
                return jsonify({"error": "Failed to create TikTok version"}), 500

            return jsonify({"success": True, "filename": result["filename"]})

    return jsonify({"error": "Clip not found"}), 404


@app.route("/api/clips/<job_id>/<clip_id>/edit", methods=["POST"])
def edit_clip_route(job_id, clip_id):
    """Export a clip with crop, speed, and filter adjustments."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json()
    crop = data.get("crop")  # {x, y, w, h} as 0-1 ratios
    speed = float(data.get("speed", 1.0))
    brightness = float(data.get("brightness", 0.0))
    contrast = float(data.get("contrast", 1.0))
    volume = float(data.get("volume", 1.0))

    for clip in job["clips"]:
        if clip["id"] == clip_id:
            clip_path = os.path.join(CLIPS_DIR, clip["filename"])
            if not os.path.exists(clip_path):
                return jsonify({"error": "Clip file not found"}), 404

            result = clip_manager.edit_clip(
                clip_path, job_id, clip_id,
                crop=crop, speed=speed,
                brightness=brightness, contrast=contrast, volume=volume
            )
            if not result:
                return jsonify({"error": "Failed to export edited clip"}), 500

            return jsonify({"success": True, "filename": result["filename"]})

    return jsonify({"error": "Clip not found"}), 404


@app.route("/api/clips/<job_id>/<clip_id>/delete", methods=["POST"])
def delete_clip(job_id, clip_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    for i, clip in enumerate(job["clips"]):
        if clip["id"] == clip_id:
            clip_manager.delete_clip(clip)
            job["clips"].pop(i)
            _save_session(job_id)
            return jsonify({"success": True})

    return jsonify({"error": "Clip not found"}), 404


def _is_valid_stream_url(url):
    """Check if the URL is a valid Twitch or YouTube VOD link."""
    url_lower = url.lower()
    patterns = ["twitch.tv/videos/", "twitch.tv/", "youtube.com/watch", "youtu.be/", "youtube.com/live/"]
    return any(p in url_lower for p in patterns)


def _get_platform_name(url):
    """Return 'Twitch' or 'YouTube' based on the URL."""
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "YouTube"
    return "Twitch"


def _save_to_library(url, video_path):
    """Move a downloaded VOD to the library with a readable name."""
    # Extract VOD ID from URL for the filename
    vod_id = re.search(r'videos/(\d+)', url)
    yt_id = re.search(r'(?:v=|youtu\.be/)([\w-]+)', url)
    if vod_id:
        name = f"twitch_{vod_id.group(1)}.mp4"
    elif yt_id:
        name = f"youtube_{yt_id.group(1)}.mp4"
    else:
        name = f"vod_{os.path.basename(video_path)}"

    lib_path = os.path.join(LIBRARY_DIR, name)

    # Don't overwrite if already saved
    if os.path.exists(lib_path):
        # Already in library, delete the temp download
        if video_path != lib_path:
            os.remove(video_path)
        return lib_path

    shutil.move(video_path, lib_path)
    return lib_path


def _run_analysis(job_id, url, api_key="", time_start="", time_end="", game_id="arc_raiders"):
    job = jobs[job_id]
    platform = _get_platform_name(url)

    def update(status, progress, message=""):
        job["status"] = status
        job["progress"] = progress
        job["message"] = message

    try:
        range_msg = ""
        if time_start or time_end:
            range_msg = f" ({time_start or '0:00'} to {time_end or 'end'})"
        update("downloading", 5, f"Downloading {platform} VOD{range_msg}...")

        video_path = clip_manager.download_vod(
            url, job_id,
            time_start=time_start or None,
            time_end=time_end or None,
            progress_callback=lambda p: update(
                "downloading", 5 + int(p * 35),
                f"Downloading{range_msg}... {int(p * 100)}%"
            )
        )

        if not video_path:
            raise Exception("Failed to download VOD. Check the URL and try again.")

        # Save to library so user doesn't have to re-download
        update("downloading", 40, "Saving to library...")
        video_path = _save_to_library(url, video_path)

        _run_analysis_on_file(job_id, video_path, api_key, time_start, time_end, game_id)

    except Exception as e:
        job["error"] = str(e)
        update("error", 0, str(e))


def _run_analysis_on_file(job_id, video_path, api_key="", time_start="", time_end="", game_id="arc_raiders"):
    """Run analysis on a local video file (from library or download)."""
    job = jobs[job_id]

    def update(status, progress, message=""):
        job["status"] = status
        job["progress"] = progress
        job["message"] = message

    try:
        job["vod_path"] = video_path
        job["vod_duration"] = clip_manager.get_vod_duration(video_path)

        use_ai = bool(api_key)

        if use_ai:
            update("analyzing", 42, "AI is watching your gameplay...")
            analyzer = GrokVisionAnalyzer(api_key, game_id=game_id)
            highlights = analyzer.analyze_frames(
                video_path,
                sample_interval_sec=8,
                progress_callback=lambda p: update(
                    "analyzing", 42 + int(p * 38),
                    f"AI analyzing frames... {int(p * 100)}%"
                )
            )
        else:
            update("analyzing", 42, "Analyzing video for highlights...")
            detector = GameDetector(game_id=game_id)
            highlights = detector.analyze_video(
                video_path,
                progress_callback=lambda p: update(
                    "analyzing", 42 + int(p * 38),
                    f"Scanning frames... {int(p * 100)}%"
                )
            )

        if not highlights:
            update("complete", 100, "Analysis complete - no highlights found")
            job["clips"] = []
            job["created_at"] = datetime.now().isoformat()
            _save_session(job_id)
            return

        update("clipping", 82, f"Extracting {len(highlights)} clips...")
        clips = clip_manager.extract_clips(
            video_path, highlights, job_id,
            progress_callback=lambda p: update(
                "clipping", 82 + int(p * 16),
                f"Cutting clip {int(p * len(highlights)) + 1} of {len(highlights)}..."
            )
        )

        job["clips"] = clips
        job["created_at"] = datetime.now().isoformat()
        update("complete", 100, f"Done! Found {len(clips)} highlight clips")
        _save_session(job_id)

    except Exception as e:
        job["error"] = str(e)
        update("error", 0, str(e))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
