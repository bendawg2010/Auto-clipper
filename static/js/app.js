// ===== Persistent State =====
// Everything saves to localStorage so closing the tab doesn't lose your settings.

const STORAGE_KEY = "autoclipper_state";

function loadState() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : {};
    } catch { return {}; }
}

function saveState() {
    const state = {
        selectedGame: selectedGame,
        apiKey: document.getElementById("api-key").value.trim(),
        vodUrl: document.getElementById("vod-url").value.trim(),
        timeStart: document.getElementById("time-start").value.trim(),
        timeEnd: document.getElementById("time-end").value.trim(),
        timeRangeOpen: !document.getElementById("time-range-wrapper").classList.contains("hidden"),
        apiKeyOpen: !document.getElementById("api-key-wrapper").classList.contains("hidden"),
        source: currentSource,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

// Save whenever the user changes anything
function hookAutoSave() {
    ["vod-url", "api-key", "time-start", "time-end"].forEach(id => {
        document.getElementById(id).addEventListener("input", saveState);
    });
    // Save on tab close / navigate away
    window.addEventListener("beforeunload", saveState);
    // Save periodically as backup
    setInterval(saveState, 5000);
}

function restoreState() {
    const state = loadState();
    if (!state || !Object.keys(state).length) return;

    if (state.selectedGame) {
        selectedGame = state.selectedGame;
    }
    if (state.apiKey) {
        document.getElementById("api-key").value = state.apiKey;
    }
    if (state.vodUrl) {
        document.getElementById("vod-url").value = state.vodUrl;
    }
    if (state.timeStart) {
        document.getElementById("time-start").value = state.timeStart;
    }
    if (state.timeEnd) {
        document.getElementById("time-end").value = state.timeEnd;
    }
    if (state.timeRangeOpen) {
        document.getElementById("time-range-wrapper").classList.remove("hidden");
        document.getElementById("time-toggle-icon").textContent = "-";
    }
    if (state.apiKeyOpen) {
        document.getElementById("api-key-wrapper").classList.remove("hidden");
        document.getElementById("api-toggle-icon").textContent = "-";
    }
    if (state.source) {
        setSource(state.source);
    }
}

// ===== Game Selection =====
let selectedGame = "arc_raiders";
let availableGames = [];

function loadGames() {
    fetch("/api/games")
        .then(res => res.json())
        .then(data => {
            availableGames = data.games || [];
            renderGameOptions();
        })
        .catch(() => {
            // Fallback if endpoint fails
            availableGames = [
                { id: "arc_raiders", name: "Arc Raiders", description: "Sci-fi co-op shooter" },
                { id: "war_thunder", name: "War Thunder", description: "Military vehicles" },
            ];
            renderGameOptions();
        });
}

function renderGameOptions() {
    const container = document.getElementById("game-options");
    container.innerHTML = availableGames.map(game => `
        <button class="game-btn ${game.id === selectedGame ? 'active' : ''}"
                onclick="selectGame('${game.id}')"
                data-game="${game.id}">
            <span class="game-btn-name">${escapeHtml(game.name)}</span>
            <span class="game-btn-desc">${escapeHtml(game.description)}</span>
        </button>
    `).join("");
}

function selectGame(gameId) {
    selectedGame = gameId;
    document.querySelectorAll(".game-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.game === gameId);
    });
    saveState();
}

// ===== Source Toggle (URL vs Upload) =====
let currentSource = "url";
let selectedFile = null;

function setSource(source) {
    currentSource = source;
    document.querySelectorAll(".source-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.source === source);
    });
    document.getElementById("url-mode").classList.toggle("hidden", source !== "url");
    document.getElementById("upload-mode").classList.toggle("hidden", source !== "upload");
    hideError();
    saveState();
}

// ===== File Upload =====
function initUpload() {
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");

    dropZone.addEventListener("click", () => fileInput.click());
    dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("drag-over"); });
    dropZone.addEventListener("dragleave", () => { dropZone.classList.remove("drag-over"); });
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
        if (e.dataTransfer.files.length > 0) handleFileSelect(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) handleFileSelect(fileInput.files[0]);
    });
}

function handleFileSelect(file) {
    const allowedExt = [".mp4", ".mkv", ".mov", ".avi", ".flv", ".ts", ".webm"];
    const ext = "." + file.name.split(".").pop().toLowerCase();
    if (!allowedExt.includes(ext)) {
        showError("Unsupported file type. Use: " + allowedExt.join(", "));
        return;
    }
    selectedFile = file;
    document.getElementById("file-name").textContent = file.name;
    document.getElementById("file-size").textContent = formatFileSize(file.size);
    document.getElementById("file-info").classList.remove("hidden");
    document.getElementById("upload-btn").classList.remove("hidden");
    document.getElementById("drop-zone").classList.add("hidden");
    hideError();
}

function clearFile() {
    selectedFile = null;
    document.getElementById("file-input").value = "";
    document.getElementById("file-info").classList.add("hidden");
    document.getElementById("upload-btn").classList.add("hidden");
    document.getElementById("drop-zone").classList.remove("hidden");
}

function startUploadAnalysis() {
    if (!selectedFile) { showError("Please select a file first"); return; }
    hideError();
    setUploading(true);
    showProgress();
    saveState();

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("api_key", document.getElementById("api-key").value.trim());
    formData.append("time_start", document.getElementById("time-start").value.trim());
    formData.append("time_end", document.getElementById("time-end").value.trim());
    formData.append("game", selectedGame);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload");
    xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
            const pct = Math.round((e.loaded / e.total) * 40);
            updateProgress("uploading", pct, `Uploading... ${Math.round(e.loaded / e.total * 100)}%`);
        }
    });
    xhr.addEventListener("load", () => {
        if (xhr.status === 200) {
            const data = JSON.parse(xhr.responseText);
            if (data.error) { showError(data.error); resetUI(); return; }
            currentJobId = data.job_id;
            startPolling();
        } else {
            try { showError(JSON.parse(xhr.responseText).error || "Upload failed"); }
            catch { showError("Upload failed. File may be too large."); }
            resetUI();
        }
    });
    xhr.addEventListener("error", () => { showError("Upload failed."); resetUI(); });
    xhr.send(formData);
}

function setUploading(uploading) {
    const btn = document.getElementById("upload-btn");
    btn.disabled = uploading;
    btn.innerHTML = uploading
        ? '<span class="spinner"></span> Uploading'
        : '<span class="btn-text">Upload &amp; Analyze</span><span class="btn-icon">&#9654;</span>';
}

// ===== App State =====
let currentJobId = null;
let currentClips = [];
let previewClipData = null;
let previewClipIndex = -1;
let pollTimer = null;
let vodDuration = 0;

// ===== Init =====
window.addEventListener("DOMContentLoaded", () => {
    restoreState();
    loadGames();
    hookAutoSave();
    loadLibrary();
    initUpload();
});

// ===== VOD Library =====
function loadLibrary() {
    fetch("/api/library")
        .then(res => res.json())
        .then(data => {
            const vods = data.vods || [];
            const section = document.getElementById("library-section");
            const list = document.getElementById("library-list");
            const count = document.getElementById("library-count");

            if (vods.length === 0) {
                section.classList.add("hidden");
                return;
            }

            section.classList.remove("hidden");
            count.textContent = vods.length;

            list.innerHTML = vods.map(vod => `
                <div class="library-item">
                    <div class="library-item-info" onclick="analyzeFromLibrary('${escapeHtml(vod.filename)}')">
                        <span class="library-item-name">${escapeHtml(vod.filename)}</span>
                        <span class="library-item-meta">
                            ${formatFileSize(vod.size)}
                            ${vod.duration ? ' &middot; ' + formatTime(vod.duration) : ''}
                        </span>
                    </div>
                    <button class="library-item-delete" onclick="deleteLibraryVod('${escapeHtml(vod.filename)}')" title="Delete">&times;</button>
                </div>
            `).join("");
        })
        .catch(() => {});
}

function analyzeFromLibrary(filename) {
    hideError();
    setAnalyzing(true);
    showProgress();

    const apiKey = document.getElementById("api-key").value.trim();
    const timeStart = document.getElementById("time-start").value.trim();
    const timeEnd = document.getElementById("time-end").value.trim();

    fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            library_file: filename,
            api_key: apiKey,
            time_start: timeStart,
            time_end: timeEnd,
            game: selectedGame,
        }),
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            showError(data.error);
            resetUI();
            return;
        }
        currentJobId = data.job_id;
        startPolling();
    })
    .catch(() => {
        showError("Failed to start analysis.");
        resetUI();
    });
}

function deleteLibraryVod(filename) {
    if (!confirm("Delete this saved VOD? This frees up storage.")) return;

    fetch(`/api/library/${encodeURIComponent(filename)}/delete`, { method: "POST" })
        .then(res => res.json())
        .then(data => {
            if (data.success) loadLibrary();
        });
}

function formatFileSize(bytes) {
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
}

// Start analysis
function startAnalysis() {
    const url = document.getElementById("vod-url").value.trim();
    const apiKey = document.getElementById("api-key").value.trim();

    if (!url) {
        showError("Please paste a Twitch or YouTube VOD link");
        return;
    }

    if (!url.includes("twitch.tv") && !url.includes("youtube.com") && !url.includes("youtu.be")) {
        showError("That doesn't look like a Twitch or YouTube URL");
        return;
    }

    hideError();
    setAnalyzing(true);
    showProgress();
    saveState();

    const timeStart = document.getElementById("time-start").value.trim();
    const timeEnd = document.getElementById("time-end").value.trim();

    fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            url,
            api_key: apiKey,
            time_start: timeStart,
            time_end: timeEnd,
            game: selectedGame,
        }),
    })
    .then((res) => res.json())
    .then((data) => {
        if (data.error) {
            showError(data.error);
            resetUI();
            return;
        }
        currentJobId = data.job_id;
        startPolling();
    })
    .catch(() => {
        showError("Failed to start analysis. Please try again.");
        resetUI();
    });
}

document.getElementById("vod-url").addEventListener("keydown", (e) => {
    if (e.key === "Enter") startAnalysis();
});

// Polling
function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(pollJob, 1500);
}

function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

function pollJob() {
    if (!currentJobId) return;

    fetch(`/api/jobs/${currentJobId}`)
        .then((res) => res.json())
        .then((data) => {
            if (data.error && !data.status) {
                showError(data.error);
                resetUI();
                stopPolling();
                return;
            }

            updateProgress(data.status, data.progress, data.message);

            if (data.status === "complete") {
                stopPolling();
                fetchClips(currentJobId);
            } else if (data.status === "error") {
                stopPolling();
                showError(data.message || data.error || "An error occurred");
                resetUI();
            }
        })
        .catch(() => {});
}

// Progress
function showProgress() {
    document.getElementById("progress-section").classList.remove("hidden");
    document.getElementById("clips-section").classList.add("hidden");
}

function updateProgress(status, progress, message) {
    document.getElementById("progress-bar").style.width = progress + "%";
    document.getElementById("progress-pct").textContent = progress + "%";
    document.getElementById("progress-message").textContent = message || "";

    const titles = {
        queued: "Queued...",
        uploading: "Uploading VOD",
        downloading: "Downloading VOD",
        analyzing: "Analyzing Gameplay",
        clipping: "Extracting Clips",
        complete: "Complete!",
        error: "Error",
    };
    document.getElementById("progress-title").textContent = titles[status] || "Processing...";
}

// Clips
function fetchClips(jobId) {
    fetch(`/api/clips/${jobId}`)
        .then((res) => res.json())
        .then((data) => {
            currentClips = data.clips || [];
            vodDuration = data.vod_duration || 0;
            renderClips();
            setAnalyzing(false);
            loadLibrary(); // Refresh — new VOD may have been saved
        })
        .catch(() => {
            showError("Failed to load clips");
            resetUI();
        });
}

function renderClips() {
    const grid = document.getElementById("clips-grid");
    const section = document.getElementById("clips-section");
    const noClips = document.getElementById("no-clips");
    const count = document.getElementById("clip-count");

    section.classList.remove("hidden");
    count.textContent = currentClips.length + " clip" + (currentClips.length !== 1 ? "s" : "");

    if (currentClips.length === 0) {
        grid.classList.add("hidden");
        noClips.classList.remove("hidden");
        return;
    }

    grid.classList.remove("hidden");
    noClips.classList.add("hidden");

    grid.innerHTML = currentClips.map((clip, i) => `
        <div class="clip-card" data-index="${i}">
            <div class="clip-thumb" onclick="previewClip(${i})">
                ${clip.thumbnail
                    ? `<img src="/static/thumbnails/${clip.thumbnail}?t=${Date.now()}" alt="${escapeHtml(clip.label)}">`
                    : `<div style="width:100%;height:100%;background:#1a1a2e;display:flex;align-items:center;justify-content:center;color:#666">No Preview</div>`
                }
                <div class="play-overlay"><span>&#9654;</span></div>
            </div>
            <div class="clip-info">
                <div class="clip-label">${escapeHtml(clip.label)}</div>
                <div class="clip-meta">
                    <span>${clip.timestamp_display} &middot; ${clip.duration}s</span>
                    <div class="confidence-bar">
                        <div class="confidence-bar-fill" style="width: ${clip.confidence * 100}%"></div>
                    </div>
                </div>
            </div>
            <div class="clip-actions">
                <button class="btn-download" onclick="event.stopPropagation(); downloadClip('${clip.id}', '${clip.filename}')">Download</button>
                <button class="btn-trim" onclick="event.stopPropagation(); previewClip(${i})">Trim</button>
                <button class="btn-delete" onclick="event.stopPropagation(); deleteClip('${clip.id}', ${i})">Remove</button>
            </div>
        </div>
    `).join("");
}

// Preview + Trim modal
function previewClip(index) {
    const clip = currentClips[index];
    if (!clip) return;

    previewClipData = clip;
    previewClipIndex = index;
    const modal = document.getElementById("preview-modal");
    const video = document.getElementById("preview-video");

    video.src = `/static/clips/${clip.filename}?t=${Date.now()}`;
    document.getElementById("modal-label").textContent = clip.label;
    document.getElementById("modal-time").textContent = `${clip.timestamp_display} - Duration: ${clip.duration}s`;

    // Set up trim controls
    const startInput = document.getElementById("trim-start");
    const endInput = document.getElementById("trim-end");
    const maxTime = vodDuration || clip.end_time + 120;

    startInput.value = clip.start_time;
    endInput.value = clip.end_time;
    startInput.max = maxTime;
    endInput.max = maxTime;

    document.getElementById("trim-start-display").textContent = formatTime(clip.start_time);
    document.getElementById("trim-end-display").textContent = formatTime(clip.end_time);
    document.getElementById("trim-duration-display").textContent = clip.duration + "s";

    document.getElementById("trim-status").textContent = "";
    document.getElementById("trim-status").className = "trim-status";

    modal.classList.remove("hidden");
    video.play().catch(() => {});
}

function onTrimInputChange() {
    const startInput = document.getElementById("trim-start");
    const endInput = document.getElementById("trim-end");
    const start = parseFloat(startInput.value);
    const end = parseFloat(endInput.value);

    document.getElementById("trim-start-display").textContent = formatTime(start);
    document.getElementById("trim-end-display").textContent = formatTime(end);
    document.getElementById("trim-duration-display").textContent = Math.max(0, (end - start)).toFixed(1) + "s";
}

function adjustTrim(field, delta) {
    const input = document.getElementById(`trim-${field}`);
    let val = parseFloat(input.value) + delta;
    val = Math.max(0, val);
    if (vodDuration > 0) val = Math.min(vodDuration, val);
    input.value = val.toFixed(1);
    onTrimInputChange();
}

function applyTrim() {
    if (!previewClipData || !currentJobId) return;

    const start = parseFloat(document.getElementById("trim-start").value);
    const end = parseFloat(document.getElementById("trim-end").value);

    if (end <= start) {
        document.getElementById("trim-status").textContent = "End must be after start";
        document.getElementById("trim-status").className = "trim-status error";
        return;
    }

    if (end - start > 300) {
        document.getElementById("trim-status").textContent = "Max clip length is 5 minutes";
        document.getElementById("trim-status").className = "trim-status error";
        return;
    }

    const statusEl = document.getElementById("trim-status");
    statusEl.textContent = "Re-cutting clip...";
    statusEl.className = "trim-status working";

    const trimBtn = document.getElementById("trim-apply-btn");
    trimBtn.disabled = true;

    fetch(`/api/clips/${currentJobId}/${previewClipData.id}/trim`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start, end }),
    })
    .then((res) => res.json())
    .then((data) => {
        trimBtn.disabled = false;

        if (data.error) {
            statusEl.textContent = data.error;
            statusEl.className = "trim-status error";
            return;
        }

        if (data.success && data.clip) {
            // Update local state
            currentClips[previewClipIndex] = data.clip;
            previewClipData = data.clip;

            // Refresh video
            const video = document.getElementById("preview-video");
            video.src = `/static/clips/${data.clip.filename}?t=${Date.now()}`;
            video.play().catch(() => {});

            document.getElementById("modal-time").textContent =
                `${data.clip.timestamp_display} - Duration: ${data.clip.duration}s`;

            statusEl.textContent = "Clip updated!";
            statusEl.className = "trim-status success";

            renderClips();
        }
    })
    .catch(() => {
        trimBtn.disabled = false;
        statusEl.textContent = "Failed to trim clip";
        statusEl.className = "trim-status error";
    });
}

function closePreview() {
    const modal = document.getElementById("preview-modal");
    const video = document.getElementById("preview-video");
    video.pause();
    video.src = "";
    modal.classList.add("hidden");
    previewClipData = null;
    previewClipIndex = -1;
}

function closeModal(event) {
    if (event.target === event.currentTarget) closePreview();
}

function downloadFromModal() {
    if (previewClipData) downloadClip(previewClipData.id, previewClipData.filename);
}

function downloadClip(clipId, filename) {
    const a = document.createElement("a");
    a.href = `/api/clips/${currentJobId}/${clipId}/download`;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function deleteClip(clipId, index) {
    if (!confirm("Remove this clip?")) return;

    fetch(`/api/clips/${currentJobId}/${clipId}/delete`, { method: "POST" })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                currentClips.splice(index, 1);
                renderClips();
            }
        });
}

// Toggles
function toggleTimeRange() {
    const wrapper = document.getElementById("time-range-wrapper");
    const icon = document.getElementById("time-toggle-icon");
    wrapper.classList.toggle("hidden");
    icon.textContent = wrapper.classList.contains("hidden") ? "+" : "-";
    saveState();
}

function toggleApiKey() {
    const wrapper = document.getElementById("api-key-wrapper");
    const icon = document.getElementById("api-toggle-icon");
    wrapper.classList.toggle("hidden");
    icon.textContent = wrapper.classList.contains("hidden") ? "+" : "-";
    saveState();
}

// Helpers
function setAnalyzing(analyzing) {
    const btn = document.getElementById("analyze-btn");
    const input = document.getElementById("vod-url");
    btn.disabled = analyzing;
    input.disabled = analyzing;
    btn.innerHTML = analyzing
        ? '<span class="spinner"></span> Analyzing'
        : '<span class="btn-text">Analyze</span><span class="btn-icon">&#9654;</span>';
}

function showError(msg) {
    const el = document.getElementById("error-msg");
    el.textContent = msg;
    el.classList.remove("hidden");
}

function hideError() {
    document.getElementById("error-msg").classList.add("hidden");
}

function resetUI() {
    setAnalyzing(false);
    setUploading(false);
    stopPolling();
    document.getElementById("progress-section").classList.add("hidden");
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function formatTime(seconds) {
    seconds = Math.round(seconds);
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    return `${m}:${String(s).padStart(2, "0")}`;
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        if (!document.getElementById("tiktok-modal").classList.contains("hidden")) {
            closeTikTok();
        } else {
            closePreview();
        }
    }
});

// ===== TikTok Editor =====
let tiktokFrame = null; // captured video frame as ImageData
let tiktokDrawing = null; // "gameplay" or "webcam"
let tiktokDragStart = null;
let tiktokRegions = { gameplay: null, webcam: null };
let tiktokCurrentPreset = "cam-top-right";

function openTikTokEditor() {
    if (!previewClipData) return;

    const video = document.getElementById("preview-video");
    const canvas = document.getElementById("tiktok-canvas");
    const ctx = canvas.getContext("2d");

    // Capture current frame from video
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 360;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    tiktokFrame = ctx.getImageData(0, 0, canvas.width, canvas.height);

    // Default drawing mode
    tiktokDrawing = "gameplay";

    // Apply default preset
    setPreset("cam-top-right");

    document.getElementById("tiktok-modal").classList.remove("hidden");
    document.getElementById("tiktok-status").textContent = "";
    document.getElementById("tiktok-status").className = "trim-status";

    drawTikTokOverlay();
}

function closeTikTok() {
    document.getElementById("tiktok-modal").classList.add("hidden");
}

function setPreset(name) {
    tiktokCurrentPreset = name;

    // Update active button
    document.querySelectorAll(".preset-btn").forEach(b => b.classList.remove("active"));
    if (event && event.target) event.target.classList.add("active");

    if (name === "cam-top-right") {
        tiktokRegions.gameplay = { x: 0, y: 0, w: 1, h: 1 };
        tiktokRegions.webcam = { x: 0.72, y: 0.02, w: 0.26, h: 0.30 };
    } else if (name === "cam-top-left") {
        tiktokRegions.gameplay = { x: 0, y: 0, w: 1, h: 1 };
        tiktokRegions.webcam = { x: 0.02, y: 0.02, w: 0.26, h: 0.30 };
    } else if (name === "cam-bottom-left") {
        tiktokRegions.gameplay = { x: 0, y: 0, w: 1, h: 1 };
        tiktokRegions.webcam = { x: 0.02, y: 0.68, w: 0.26, h: 0.30 };
    } else if (name === "no-cam") {
        tiktokRegions.gameplay = { x: 0, y: 0, w: 1, h: 1 };
        tiktokRegions.webcam = null;
    } else if (name === "custom") {
        tiktokRegions.gameplay = { x: 0.05, y: 0.05, w: 0.9, h: 0.9 };
        tiktokRegions.webcam = { x: 0.7, y: 0.02, w: 0.28, h: 0.30 };
    }

    drawTikTokOverlay();
    drawTikTokPreview();
}

function drawTikTokOverlay() {
    const canvas = document.getElementById("tiktok-canvas");
    const ctx = canvas.getContext("2d");

    // Restore original frame
    if (tiktokFrame) ctx.putImageData(tiktokFrame, 0, 0);

    const w = canvas.width, h = canvas.height;

    // Draw gameplay region (green)
    if (tiktokRegions.gameplay) {
        const r = tiktokRegions.gameplay;
        ctx.strokeStyle = "#00ff00";
        ctx.lineWidth = 3;
        ctx.setLineDash([8, 4]);
        ctx.strokeRect(r.x * w, r.y * h, r.w * w, r.h * h);
        ctx.setLineDash([]);
        ctx.fillStyle = "rgba(0, 255, 0, 0.1)";
        ctx.fillRect(r.x * w, r.y * h, r.w * w, r.h * h);
        ctx.fillStyle = "#00ff00";
        ctx.font = "bold 14px sans-serif";
        ctx.fillText("GAMEPLAY", r.x * w + 6, r.y * h + 18);
    }

    // Draw webcam region (blue)
    if (tiktokRegions.webcam) {
        const r = tiktokRegions.webcam;
        ctx.strokeStyle = "#00aaff";
        ctx.lineWidth = 3;
        ctx.setLineDash([8, 4]);
        ctx.strokeRect(r.x * w, r.y * h, r.w * w, r.h * h);
        ctx.setLineDash([]);
        ctx.fillStyle = "rgba(0, 170, 255, 0.15)";
        ctx.fillRect(r.x * w, r.y * h, r.w * w, r.h * h);
        ctx.fillStyle = "#00aaff";
        ctx.font = "bold 14px sans-serif";
        ctx.fillText("WEBCAM", r.x * w + 6, r.y * h + 18);
    }
}

function drawTikTokPreview() {
    const srcCanvas = document.getElementById("tiktok-canvas");
    const preview = document.getElementById("tiktok-preview");
    const ctx = preview.getContext("2d");
    const sw = srcCanvas.width, sh = srcCanvas.height;

    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, 180, 320);

    if (tiktokRegions.webcam) {
        // Stacked: gameplay 70%, webcam 30%
        const gpH = 224; // 70% of 320
        const wcH = 96;  // 30% of 320

        if (tiktokFrame) {
            // Draw gameplay crop
            const g = tiktokRegions.gameplay;
            const tempCanvas = document.createElement("canvas");
            tempCanvas.width = sw; tempCanvas.height = sh;
            tempCanvas.getContext("2d").putImageData(tiktokFrame, 0, 0);

            ctx.drawImage(tempCanvas,
                g.x * sw, g.y * sh, g.w * sw, g.h * sh,
                0, 0, 180, gpH);

            // Draw webcam crop
            const w = tiktokRegions.webcam;
            ctx.drawImage(tempCanvas,
                w.x * sw, w.y * sh, w.w * sw, w.h * sh,
                0, gpH, 180, wcH);

            // Divider line
            ctx.strokeStyle = "#333";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(0, gpH);
            ctx.lineTo(180, gpH);
            ctx.stroke();
        }
    } else {
        // Gameplay only
        if (tiktokFrame) {
            const g = tiktokRegions.gameplay;
            const tempCanvas = document.createElement("canvas");
            tempCanvas.width = sw; tempCanvas.height = sh;
            tempCanvas.getContext("2d").putImageData(tiktokFrame, 0, 0);

            ctx.drawImage(tempCanvas,
                g.x * sw, g.y * sh, g.w * sw, g.h * sh,
                0, 0, 180, 320);
        }
    }
}

// Canvas mouse + touch interaction for custom drawing
(function() {
    let drawing = false;
    let startX, startY;

    function getPos(e, canvas) {
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        let clientX, clientY;
        if (e.touches && e.touches.length > 0) {
            clientX = e.touches[0].clientX;
            clientY = e.touches[0].clientY;
        } else if (e.changedTouches && e.changedTouches.length > 0) {
            clientX = e.changedTouches[0].clientX;
            clientY = e.changedTouches[0].clientY;
        } else {
            clientX = e.clientX;
            clientY = e.clientY;
        }
        return {
            x: (clientX - rect.left) * scaleX,
            y: (clientY - rect.top) * scaleY,
        };
    }

    function onStart(e) {
        if (tiktokCurrentPreset !== "custom") return;
        e.preventDefault();
        drawing = true;
        const canvas = document.getElementById("tiktok-canvas");
        const pos = getPos(e, canvas);
        startX = pos.x;
        startY = pos.y;
    }

    function onMove(e) {
        if (!drawing) return;
        e.preventDefault();
        const canvas = document.getElementById("tiktok-canvas");
        const pos = getPos(e, canvas);

        const x = Math.min(startX, pos.x) / canvas.width;
        const y = Math.min(startY, pos.y) / canvas.height;
        const w = Math.abs(pos.x - startX) / canvas.width;
        const h = Math.abs(pos.y - startY) / canvas.height;

        tiktokRegions[tiktokDrawing] = { x, y, w, h };
        drawTikTokOverlay();
        drawTikTokPreview();
    }

    function onEnd() { drawing = false; }

    document.addEventListener("DOMContentLoaded", () => {
        const canvas = document.getElementById("tiktok-canvas");

        // Mouse events
        canvas.addEventListener("mousedown", onStart);
        canvas.addEventListener("mousemove", onMove);
        canvas.addEventListener("mouseup", onEnd);

        // Touch events
        canvas.addEventListener("touchstart", onStart, { passive: false });
        canvas.addEventListener("touchmove", onMove, { passive: false });
        canvas.addEventListener("touchend", onEnd);

        // Right-click / long-press to switch region
        canvas.addEventListener("contextmenu", (e) => {
            e.preventDefault();
            tiktokDrawing = tiktokDrawing === "gameplay" ? "webcam" : "gameplay";
            const status = document.getElementById("tiktok-status");
            status.textContent = `Now drawing: ${tiktokDrawing}`;
            status.className = "trim-status";
        });

        // Long press for touch (switch region)
        let longPressTimer = null;
        canvas.addEventListener("touchstart", (e) => {
            longPressTimer = setTimeout(() => {
                tiktokDrawing = tiktokDrawing === "gameplay" ? "webcam" : "gameplay";
                const status = document.getElementById("tiktok-status");
                status.textContent = `Now drawing: ${tiktokDrawing}`;
                status.className = "trim-status";
                drawing = false; // cancel the draw
            }, 600);
        });
        canvas.addEventListener("touchend", () => { clearTimeout(longPressTimer); });
        canvas.addEventListener("touchmove", () => { clearTimeout(longPressTimer); });
    });
})();

function switchDrawingRegion() {
    tiktokDrawing = tiktokDrawing === "gameplay" ? "webcam" : "gameplay";
    document.getElementById("tiktok-drawing-label").textContent =
        tiktokDrawing.charAt(0).toUpperCase() + tiktokDrawing.slice(1);
    const status = document.getElementById("tiktok-status");
    status.textContent = `Now drawing: ${tiktokDrawing}`;
    status.className = "trim-status";
}

function exportTikTok() {
    if (!previewClipData || !currentJobId) return;

    const statusEl = document.getElementById("tiktok-status");
    const btn = document.getElementById("tiktok-export-btn");
    statusEl.textContent = "Creating TikTok version...";
    statusEl.className = "trim-status working";
    btn.disabled = true;

    const layout = tiktokRegions.webcam ? "stacked" : "gameplay_only";

    fetch(`/api/clips/${currentJobId}/${previewClipData.id}/tiktok`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            gameplay: tiktokRegions.gameplay,
            webcam: tiktokRegions.webcam,
            layout: layout,
        }),
    })
    .then(res => res.json())
    .then(data => {
        btn.disabled = false;
        if (data.error) {
            statusEl.textContent = data.error;
            statusEl.className = "trim-status error";
            return;
        }
        if (data.success) {
            statusEl.textContent = "Done! Downloading...";
            statusEl.className = "trim-status success";

            // Trigger download
            const a = document.createElement("a");
            a.href = `/static/clips/${data.filename}`;
            a.download = data.filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    })
    .catch(() => {
        btn.disabled = false;
        statusEl.textContent = "Failed to create TikTok version";
        statusEl.className = "trim-status error";
    });
}
