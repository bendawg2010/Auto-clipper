import os
import uuid
import subprocess
import time
import yt_dlp


class ClipManager:
    """Handles downloading VODs, extracting clips, and managing clip files."""

    def __init__(self, clips_dir, thumbnails_dir, downloads_dir):
        self.clips_dir = clips_dir
        self.thumbnails_dir = thumbnails_dir
        self.downloads_dir = downloads_dir

    def download_vod(self, url, job_id, time_start=None, time_end=None, progress_callback=None):
        """Download a Twitch VOD using yt-dlp, optionally a time range."""
        output_path = os.path.join(self.downloads_dir, f"{job_id}.mp4")

        last_progress = [0]
        download_start_time = [None]
        # Estimate expected duration in seconds for time-based progress
        expected_duration = [None]
        if time_start or time_end:
            start_sec = _parse_time_to_seconds(time_start or "0") or 0
            end_sec = _parse_time_to_seconds(time_end) if time_end else None
            if end_sec is not None:
                expected_duration[0] = end_sec - start_sec

        def progress_hook(d):
            if progress_callback and d["status"] == "downloading":
                if download_start_time[0] is None:
                    download_start_time[0] = time.time()

                pct = None

                # Method 1: total bytes known
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    pct = downloaded / total

                # Method 2: fragment-based (used with download_ranges)
                if pct is None:
                    frag_idx = d.get("fragment_index")
                    frag_count = d.get("fragment_count")
                    if frag_idx is not None and frag_count and frag_count > 0:
                        pct = frag_idx / frag_count

                # Method 3: parse _percent_str from yt-dlp
                if pct is None:
                    pct_str = d.get("_percent_str", "").strip().rstrip("%")
                    try:
                        pct = float(pct_str) / 100
                    except (ValueError, TypeError):
                        pass

                # Method 4: estimate from elapsed time vs expected video duration
                # Twitch downloads are roughly real-time to 3x speed
                if pct is None and expected_duration[0] and download_start_time[0]:
                    elapsed = time.time() - download_start_time[0]
                    # Assume download speed is ~2x real-time on average
                    estimated_total_time = expected_duration[0] / 2.0
                    if estimated_total_time > 0:
                        pct = min(elapsed / estimated_total_time, 0.95)

                # Method 5: check downloaded file size growth
                if pct is None and os.path.exists(output_path):
                    try:
                        file_size = os.path.getsize(output_path)
                        # Rough estimate: 720p Twitch is ~2-4 MB/s, use 3 MB/s
                        if expected_duration[0]:
                            est_total = expected_duration[0] * 3 * 1024 * 1024
                            pct = min(file_size / est_total, 0.95)
                    except OSError:
                        pass

                if pct is not None and pct - last_progress[0] >= 0.01:
                    last_progress[0] = pct
                    progress_callback(min(pct, 0.99))

            elif progress_callback and d["status"] == "finished":
                progress_callback(1.0)

        ydl_opts = {
            "format": "best[height<=720]/best",
            "outtmpl": output_path,
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
        }

        # Time range for partial downloads
        if time_start or time_end:
            start_sec = _parse_time_to_seconds(time_start or "0") or 0
            end_sec = _parse_time_to_seconds(time_end) if time_end else float("inf")
            if end_sec is None:
                end_sec = float("inf")
            ydl_opts["download_ranges"] = yt_dlp.utils.download_range_func(
                None, [(start_sec, end_sec)]
            )
            ydl_opts["force_keyframes_at_cuts"] = True

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(output_path):
            return output_path

        return None

    def get_vod_path(self, job_id):
        """Get the path to a downloaded VOD if it still exists."""
        path = os.path.join(self.downloads_dir, f"{job_id}.mp4")
        return path if os.path.exists(path) else None

    def get_vod_duration(self, video_path):
        """Get the duration of a video file in seconds."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
        return 0

    def extract_clips(self, video_path, highlights, job_id, progress_callback=None):
        """Extract clip segments from the downloaded video using ffmpeg."""
        clips = []

        for i, highlight in enumerate(highlights):
            clip_id = str(uuid.uuid4())[:8]
            filename = f"{job_id}_{clip_id}.mp4"
            clip_path = os.path.join(self.clips_dir, filename)
            thumb_filename = f"{job_id}_{clip_id}.jpg"
            thumb_path = os.path.join(self.thumbnails_dir, thumb_filename)

            start_time = max(0, highlight["timestamp"] - highlight.get("pre_pad", 8))
            duration = highlight.get("duration", 25)

            # Extract clip with ffmpeg
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_time),
                "-i", video_path,
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                clip_path,
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=180)

            if result.returncode != 0 or not os.path.exists(clip_path):
                continue

            # Generate thumbnail at the midpoint of the clip
            thumb_time = start_time + duration / 2
            thumb_cmd = [
                "ffmpeg", "-y",
                "-ss", str(thumb_time),
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", "5",
                thumb_path,
            ]
            subprocess.run(thumb_cmd, capture_output=True, timeout=30)

            clip_info = {
                "id": clip_id,
                "filename": filename,
                "thumbnail": thumb_filename if os.path.exists(thumb_path) else None,
                "start_time": round(start_time, 1),
                "end_time": round(start_time + duration, 1),
                "duration": round(duration, 1),
                "label": highlight.get("label", "Highlight"),
                "confidence": highlight.get("confidence", 0.5),
                "timestamp_display": _format_time(start_time),
            }
            clips.append(clip_info)

            if progress_callback:
                progress_callback((i + 1) / len(highlights))

        return clips

    def reclip(self, video_path, job_id, clip_id, new_start, new_end):
        """Re-extract a clip with new start/end times from the VOD."""
        duration = new_end - new_start
        if duration <= 0 or duration > 300:
            return None

        filename = f"{job_id}_{clip_id}_trim.mp4"
        clip_path = os.path.join(self.clips_dir, filename)
        thumb_filename = f"{job_id}_{clip_id}_trim.jpg"
        thumb_path = os.path.join(self.thumbnails_dir, thumb_filename)

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(new_start),
            "-i", video_path,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            clip_path,
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=180)
        if result.returncode != 0 or not os.path.exists(clip_path):
            return None

        # Thumbnail
        thumb_cmd = [
            "ffmpeg", "-y",
            "-ss", str(new_start + duration / 2),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "5",
            thumb_path,
        ]
        subprocess.run(thumb_cmd, capture_output=True, timeout=30)

        return {
            "filename": filename,
            "thumbnail": thumb_filename if os.path.exists(thumb_path) else None,
            "start_time": round(new_start, 1),
            "end_time": round(new_end, 1),
            "duration": round(duration, 1),
            "timestamp_display": _format_time(new_start),
        }

    def edit_clip(self, clip_path, job_id, clip_id, crop=None, speed=1.0,
                  brightness=0.0, contrast=1.0, volume=1.0):
        """
        Export a clip with crop, speed, and filter adjustments.

        Args:
            clip_path: Path to the source clip file
            job_id: Job identifier
            clip_id: Clip identifier
            crop: {"x": float, "y": float, "w": float, "h": float} as 0-1 ratios, or None
            speed: Playback speed multiplier (0.25-4.0)
            brightness: -1.0 to 1.0
            contrast: 0.5 to 2.0
            volume: 0.0 to 3.0

        Returns:
            {"filename": str} or None on failure
        """
        if not os.path.exists(clip_path):
            return None

        filename = f"{job_id}_{clip_id}_edit.mp4"
        out_path = os.path.join(self.clips_dir, filename)

        # Get source dimensions for crop
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            clip_path,
        ]
        probe = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        if probe.returncode != 0:
            return None
        src_w, src_h = [int(x) for x in probe.stdout.strip().split(",")]

        # Build video filter chain
        vfilters = []

        # Crop
        if crop:
            cx = int(crop["x"] * src_w)
            cy = int(crop["y"] * src_h)
            cw = int(crop["w"] * src_w)
            ch = int(crop["h"] * src_h)
            # Ensure even dimensions for h264
            cw = cw - (cw % 2)
            ch = ch - (ch % 2)
            if cw > 0 and ch > 0:
                vfilters.append(f"crop={cw}:{ch}:{cx}:{cy}")

        # Speed
        speed = max(0.25, min(4.0, speed))
        if speed != 1.0:
            vfilters.append(f"setpts={1.0/speed}*PTS")

        # Brightness and contrast (eq filter)
        brightness = max(-1.0, min(1.0, brightness))
        contrast = max(0.5, min(2.0, contrast))
        if brightness != 0.0 or contrast != 1.0:
            vfilters.append(f"eq=brightness={brightness}:contrast={contrast}")

        # Ensure even output dimensions
        vfilters.append("pad=ceil(iw/2)*2:ceil(ih/2)*2")

        # Build audio filter chain
        afilters = []
        volume = max(0.0, min(3.0, volume))
        if volume != 1.0:
            afilters.append(f"volume={volume}")
        if speed != 1.0:
            afilters.append(f"atempo={speed}")

        cmd = [
            "ffmpeg", "-y",
            "-i", clip_path,
        ]

        vf_str = ",".join(vfilters) if vfilters else None
        af_str = ",".join(afilters) if afilters else None

        if vf_str:
            cmd += ["-vf", vf_str]
        if af_str:
            cmd += ["-af", af_str]

        cmd += [
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            out_path,
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0 or not os.path.exists(out_path):
            print(f"  [Edit] ffmpeg error: {result.stderr.decode('utf-8', errors='replace')[-300:]}")
            return None

        return {"filename": filename}

    def delete_clip(self, clip):
        """Delete a clip and its thumbnail."""
        clip_path = os.path.join(self.clips_dir, clip["filename"])
        if os.path.exists(clip_path):
            os.remove(clip_path)

        if clip.get("thumbnail"):
            thumb_path = os.path.join(self.thumbnails_dir, clip["thumbnail"])
            if os.path.exists(thumb_path):
                os.remove(thumb_path)

    def make_tiktok(self, clip_path, job_id, clip_id, gameplay_region, webcam_region, layout="stacked"):
        """
        Convert a clip to TikTok vertical format (1080x1920) by cropping
        gameplay and webcam regions and compositing them.

        Args:
            clip_path: Path to the source clip
            job_id: Job identifier
            clip_id: Clip identifier
            gameplay_region: {"x": float, "y": float, "w": float, "h": float} as 0-1 ratios
            webcam_region: {"x": float, "y": float, "w": float, "h": float} as 0-1 ratios, or None
            layout: "stacked" (gameplay top, webcam bottom) or "gameplay_only"

        Returns:
            {"filename": str} or None on failure
        """
        if not os.path.exists(clip_path):
            return None

        # Get source video dimensions
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            clip_path,
        ]
        probe = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        if probe.returncode != 0:
            return None
        src_w, src_h = [int(x) for x in probe.stdout.strip().split(",")]

        out_w, out_h = 1080, 1920
        filename = f"{job_id}_{clip_id}_tiktok.mp4"
        out_path = os.path.join(self.clips_dir, filename)

        # Convert ratio-based regions to pixel coordinates
        gx = int(gameplay_region["x"] * src_w)
        gy = int(gameplay_region["y"] * src_h)
        gw = int(gameplay_region["w"] * src_w)
        gh = int(gameplay_region["h"] * src_h)

        if webcam_region and layout == "stacked":
            wx = int(webcam_region["x"] * src_w)
            wy = int(webcam_region["y"] * src_h)
            ww = int(webcam_region["w"] * src_w)
            wh = int(webcam_region["h"] * src_h)

            # Gameplay takes top 70%, webcam takes bottom 30%
            gameplay_h = int(out_h * 0.70)
            webcam_h = out_h - gameplay_h

            filter_complex = (
                f"[0:v]crop={gw}:{gh}:{gx}:{gy},scale={out_w}:{gameplay_h}:force_original_aspect_ratio=decrease,"
                f"pad={out_w}:{gameplay_h}:(ow-iw)/2:(oh-ih)/2:color=black[top];"
                f"[0:v]crop={ww}:{wh}:{wx}:{wy},scale={out_w}:{webcam_h}:force_original_aspect_ratio=decrease,"
                f"pad={out_w}:{webcam_h}:(ow-iw)/2:(oh-ih)/2:color=black[bot];"
                f"[top][bot]vstack=inputs=2[out]"
            )
        else:
            # Gameplay only - fill the whole vertical frame
            filter_complex = (
                f"[0:v]crop={gw}:{gh}:{gx}:{gy},scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,"
                f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=black[out]"
            )

        cmd = [
            "ffmpeg", "-y",
            "-i", clip_path,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            out_path,
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0 or not os.path.exists(out_path):
            print(f"  [TikTok] ffmpeg error: {result.stderr.decode('utf-8', errors='replace')[-300:]}")
            return None

        return {"filename": filename}

    def cleanup_download(self, video_path):
        """Remove the downloaded VOD file."""
        if video_path and os.path.exists(video_path):
            os.remove(video_path)


def _format_time(seconds):
    """Format seconds into HH:MM:SS display string."""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _parse_time_to_seconds(time_str):
    """Parse a time string like '1:30:00' or '45:00' or '90' into seconds."""
    time_str = time_str.strip()
    if not time_str or time_str == "inf":
        return None

    parts = time_str.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        else:
            return float(parts[0])
    except (ValueError, IndexError):
        return None


def _make_download_sections(start_str, end_str):
    """Create a yt-dlp download_sections string for partial downloads."""
    start_sec = _parse_time_to_seconds(start_str)
    end_sec = _parse_time_to_seconds(end_str)

    if start_sec is not None and end_sec is not None:
        return f"*{start_sec}-{end_sec}"
    elif start_sec is not None:
        return f"*{start_sec}-inf"
    elif end_sec is not None:
        return f"*0-{end_sec}"

    return None
