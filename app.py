import os
import uuid
import threading
from flask import Flask, render_template, request, jsonify, send_from_directory

from analysis.detector import GameDetector
from analysis.ai_analyzer import GrokVisionAnalyzer
from analysis.game_profiles import get_all_games
from clip_manager import ClipManager

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24).hex()
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 * 1024  # 10 GB for VOD uploads

UPLOADS_DIR_NAME = "uploads"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIPS_DIR = os.path.join(BASE_DIR, "static", "clips")
THUMBNAILS_DIR = os.path.join(BASE_DIR, "static", "thumbnails")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
UPLOADS_DIR = os.path.join(BASE_DIR, UPLOADS_DIR_NAME)

os.makedirs(CLIPS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

jobs = {}
clip_manager = ClipManager(CLIPS_DIR, THUMBNAILS_DIR, DOWNLOADS_DIR)


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
    api_key = data.get("api_key", "").strip()
    time_start = data.get("time_start", "").strip()
    time_end = data.get("time_end", "").strip()
    game_id = data.get("game", "arc_raiders").strip()

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


@app.route("/api/upload", methods=["POST"])
def upload_vod():
    """Accept a VOD file upload and start analysis."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    # Validate file extension
    allowed_ext = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts", ".webm"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        return jsonify({"error": f"Unsupported file type. Use: {', '.join(allowed_ext)}"}), 400

    api_key = request.form.get("api_key", "").strip()
    time_start = request.form.get("time_start", "").strip()
    time_end = request.form.get("time_end", "").strip()
    game_id = request.form.get("game", "arc_raiders").strip()

    job_id = str(uuid.uuid4())[:8]
    upload_path = os.path.join(UPLOADS_DIR, f"{job_id}{ext}")

    # Save uploaded file
    file.save(upload_path)

    jobs[job_id] = {
        "status": "analyzing",
        "progress": 42,
        "message": "File uploaded! Analyzing...",
        "clips": [],
        "error": None,
        "url": f"upload:{file.filename}",
        "vod_path": None,
        "vod_duration": 0,
    }

    thread = threading.Thread(
        target=_run_analysis_on_file,
        args=(job_id, upload_path, api_key, time_start, time_end, game_id),
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


@app.route("/api/clips/<job_id>/<clip_id>/delete", methods=["POST"])
def delete_clip(job_id, clip_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    for i, clip in enumerate(job["clips"]):
        if clip["id"] == clip_id:
            clip_manager.delete_clip(clip)
            job["clips"].pop(i)
            return jsonify({"success": True})

    return jsonify({"error": "Clip not found"}), 404


def _is_valid_stream_url(url):
    """Check if the URL is a valid Twitch or YouTube VOD link."""
    url_lower = url.lower()
    twitch_patterns = ["twitch.tv/videos/", "twitch.tv/"]
    youtube_patterns = ["youtube.com/watch", "youtu.be/", "youtube.com/live/"]
    all_patterns = twitch_patterns + youtube_patterns
    return any(pattern in url_lower for pattern in all_patterns)


def _get_platform_name(url):
    """Return 'Twitch' or 'YouTube' based on the URL."""
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "YouTube"
    return "Twitch"


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
            raise Exception(f"Failed to download VOD from {platform}. Check the URL and try again.")

        _analyze_video_file(job_id, job, video_path, api_key, game_id, update)

    except Exception as e:
        job["error"] = str(e)
        update("error", 0, str(e))


def _run_analysis_on_file(job_id, file_path, api_key="", time_start="", time_end="", game_id="arc_raiders"):
    """Run analysis on an uploaded file (skips download step)."""
    job = jobs[job_id]

    def update(status, progress, message=""):
        job["status"] = status
        job["progress"] = progress
        job["message"] = message

    try:
        # If time range specified, trim the uploaded file first
        if time_start or time_end:
            update("analyzing", 40, "Trimming to selected time range...")
            trimmed_path = clip_manager.trim_upload(file_path, job_id, time_start, time_end)
            if trimmed_path:
                file_path = trimmed_path

        _analyze_video_file(job_id, job, file_path, api_key, game_id, update)

    except Exception as e:
        job["error"] = str(e)
        update("error", 0, str(e))


def _analyze_video_file(job_id, job, video_path, api_key, game_id, update):
    """Shared analysis logic for both URL downloads and file uploads."""
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
    update("complete", 100, f"Done! Found {len(clips)} highlight clips")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
