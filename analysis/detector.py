import cv2
import numpy as np

from analysis.game_profiles import get_profile


class GameDetector:
    """
    Detects exciting moments in gameplay by analyzing video frames
    using a game-specific detection profile.

    The detector samples frames at a configurable rate, scores each frame
    window for "action intensity", and returns timestamps above a threshold.
    """

    def __init__(self, game_id="arc_raiders", sample_fps=2, window_seconds=3):
        """
        Args:
            game_id: Which game profile to use (e.g. "arc_raiders", "war_thunder")
            sample_fps: Frames to analyze per second (lower = faster, less precise)
            window_seconds: Sliding window size for grouping action
        """
        self.profile = get_profile(game_id)
        self.sample_fps = sample_fps
        self.window_seconds = window_seconds
        self.intensity_threshold = self.profile["intensity_threshold"]

    def analyze_video(self, video_path, progress_callback=None):
        """
        Analyze a video file and return a list of highlight timestamps.

        Returns:
            List of dicts: [{"timestamp": float, "duration": float,
                             "label": str, "confidence": float}, ...]
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        frame_interval = max(1, int(fps / self.sample_fps))
        frames_to_analyze = total_frames // frame_interval

        scores = []
        prev_frame_gray = None

        frame_idx = 0
        analyzed = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = frame_idx / fps
                score, label = self._score_frame(frame, prev_frame_gray)

                scores.append({"score": score, "label": label, "timestamp": timestamp})

                if score >= self.intensity_threshold * 0.5:
                    mins = int(timestamp) // 60
                    secs = int(timestamp) % 60
                    print(f"  [CV] {mins}:{secs:02d} - score:{score:.3f} - {label}")

                prev_frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                analyzed += 1

                if progress_callback and analyzed % 20 == 0:
                    progress_callback(analyzed / max(frames_to_analyze, 1))

            frame_idx += 1

        cap.release()

        if progress_callback:
            progress_callback(1.0)

        top_scores = sorted(scores, key=lambda s: s["score"], reverse=True)[:10]
        print(f"  [CV] Game: {self.profile['name']}")
        print(f"  [CV] Analyzed {analyzed} frames over {duration:.0f}s")
        score_strs = [f'{s["score"]:.3f}@{int(s["timestamp"])}s' for s in top_scores]
        print(f"  [CV] Top scores: {score_strs}")
        print(f"  [CV] Threshold: {self.intensity_threshold}")

        highlights = self._find_highlights(scores, duration)
        print(f"  [CV] Found {len(highlights)} highlights")
        for h in highlights:
            print(f"  [CV]   -> {h['label']} at {int(h['timestamp'])}s ({h['duration']}s, conf:{h['confidence']})")
        return highlights

    def _score_frame(self, frame, prev_gray):
        """
        Score a single frame for action intensity using the game profile.
        Returns (score: float 0-1, label: str).
        """
        h, w = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        component_scores = {}
        label_map = {}
        weights = {}

        # Process each detector from the profile
        for det_id, det in self.profile["detectors"].items():
            label_map[det_id] = det["label"]
            weights[det_id] = det["weight"]

            if det["region"] == "edges":
                # Edge detection (damage indicators) — check all 4 edges
                edge_size = det.get("edge_size", 0.10)
                edges = [
                    hsv[0:int(h * edge_size), :],              # top
                    hsv[int(h * (1 - edge_size)):, :],         # bottom
                    hsv[:, 0:int(w * edge_size)],              # left
                    hsv[:, int(w * (1 - edge_size)):],         # right
                ]
                best = 0
                for edge in edges:
                    mask1 = cv2.inRange(edge, det["lower"], det["upper"])
                    density = np.count_nonzero(mask1) / max(edge.shape[0] * edge.shape[1], 1)
                    if "lower2" in det:
                        mask2 = cv2.inRange(edge, det["lower2"], det["upper2"])
                        density += np.count_nonzero(mask2) / max(edge.shape[0] * edge.shape[1], 1)
                    best = max(best, density)
                component_scores[det_id] = min(best * det["multiplier"], 1.0)

            elif det["region"] == "full":
                # Full-frame detection
                mask = cv2.inRange(hsv, det["lower"], det["upper"])
                density = np.count_nonzero(mask) / max(mask.size, 1)
                component_scores[det_id] = min(density * det["multiplier"], 1.0)

            else:
                # Region-based detection [y1, y2, x1, x2]
                y1, y2, x1, x2 = det["region"]
                region = hsv[int(h * y1):int(h * y2), int(w * x1):int(w * x2)]
                mask = cv2.inRange(region, det["lower"], det["upper"])
                density = np.count_nonzero(mask) / max(mask.size, 1)
                if "lower2" in det:
                    mask2 = cv2.inRange(region, det["lower2"], det["upper2"])
                    density += np.count_nonzero(mask2) / max(mask2.size, 1)
                component_scores[det_id] = min(density * det["multiplier"], 1.0)

        # Motion detection
        motion_weight = self.profile.get("motion_weight", 0.10)
        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            motion = np.mean(diff) / 255.0
            component_scores["motion"] = min(motion * self.profile.get("motion_multiplier", 3), 1.0)
        else:
            component_scores["motion"] = 0
        weights["motion"] = motion_weight
        label_map["motion"] = "Intense Action"

        # Brightness spike
        brightness_weight = self.profile.get("brightness_weight", 0.05)
        brightness = np.mean(gray) / 255.0
        threshold = self.profile.get("brightness_threshold", 0.6)
        mult = self.profile.get("brightness_multiplier", 3)
        brightness_spike = max(0, brightness - threshold) * mult
        component_scores["brightness"] = min(brightness_spike, 1.0)
        weights["brightness"] = brightness_weight
        label_map["brightness"] = "Flash Event"

        # Weighted combination
        total_score = sum(component_scores.get(k, 0) * weights.get(k, 0) for k in weights)

        # Determine the dominant label
        best_component = max(component_scores, key=component_scores.get)
        label = label_map.get(best_component, "Highlight")

        return total_score, label

    def _find_highlights(self, scores, total_duration):
        """
        Group high-scoring frames into highlight windows using a sliding
        window approach, then merge overlapping windows.
        """
        if not scores:
            return []

        window_frames = int(self.window_seconds * self.sample_fps)
        window_scores = []

        for i in range(len(scores)):
            window_end = min(i + window_frames, len(scores))
            window_slice = scores[i:window_end]
            avg_score = sum(s["score"] for s in window_slice) / len(window_slice)

            label_counts = {}
            for s in window_slice:
                label_counts[s["label"]] = label_counts.get(s["label"], 0) + s["score"]
            dominant_label = max(label_counts, key=label_counts.get) if label_counts else "Highlight"

            window_scores.append({
                "start_idx": i,
                "timestamp": scores[i]["timestamp"],
                "avg_score": avg_score,
                "label": dominant_label,
            })

        peaks = [w for w in window_scores if w["avg_score"] >= self.intensity_threshold]

        if not peaks:
            sorted_windows = sorted(window_scores, key=lambda w: w["avg_score"], reverse=True)
            fallback_ratio = self.profile.get("fallback_threshold_ratio", 0.3)
            fallback_threshold = self.intensity_threshold * fallback_ratio
            # Only take top 5 fallback clips (not 10) to avoid low-quality clips
            peaks = [w for w in sorted_windows[:5] if w["avg_score"] >= fallback_threshold]

        if not peaks:
            return []

        merged = self._merge_highlights(peaks)
        merged.sort(key=lambda h: h["timestamp"])
        return merged

    def _merge_highlights(self, peaks, merge_gap=None):
        """Merge highlights that are within merge_gap seconds of each other."""
        if not peaks:
            return []

        if merge_gap is None:
            merge_gap = self.profile.get("merge_gap", 8)

        peaks.sort(key=lambda p: p["timestamp"])

        merged = []
        current = {
            "timestamp": peaks[0]["timestamp"],
            "end_time": peaks[0]["timestamp"] + self.window_seconds,
            "label": peaks[0]["label"],
            "confidence": peaks[0]["avg_score"],
            "peak_score": peaks[0]["avg_score"],
        }

        for peak in peaks[1:]:
            if peak["timestamp"] <= current["end_time"] + merge_gap:
                current["end_time"] = peak["timestamp"] + self.window_seconds
                current["peak_score"] = max(current["peak_score"], peak["avg_score"])
                current["confidence"] = (current["confidence"] + peak["avg_score"]) / 2
                if peak["avg_score"] > current["peak_score"] * 0.9:
                    current["label"] = peak["label"]
            else:
                merged.append(self._finalize_highlight(current))
                current = {
                    "timestamp": peak["timestamp"],
                    "end_time": peak["timestamp"] + self.window_seconds,
                    "label": peak["label"],
                    "confidence": peak["avg_score"],
                    "peak_score": peak["avg_score"],
                }

        merged.append(self._finalize_highlight(current))
        return merged

    def _finalize_highlight(self, highlight):
        """Convert a merged highlight window into the output format."""
        duration = highlight["end_time"] - highlight["timestamp"]
        min_dur = self.profile.get("min_clip_duration", 20)
        max_dur = self.profile.get("max_clip_duration", 60)
        extension = self.profile.get("clip_extension", 10)
        duration = max(min_dur, min(max_dur, duration + extension))

        return {
            "timestamp": highlight["timestamp"],
            "duration": duration,
            "pre_pad": self.profile.get("pre_pad", 8),
            "label": highlight["label"],
            "confidence": round(min(highlight["confidence"] * 1.5, 1.0), 2),
        }


# Backwards compatibility alias
ArcRaidersDetector = GameDetector
