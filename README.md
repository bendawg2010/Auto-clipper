# Auto-Clipper (Beta)

Automatically find the best moments in your Twitch or YouTube VODs — kills, combat, explosions, and more. Paste a link or upload a file, get highlight clips.

**Supports:** Arc Raiders, War Thunder (more coming)

---

## What It Does

1. **Pick** your game from the menu
2. **Paste** a Twitch/YouTube VOD link — or **upload** a video file from your computer
3. **Wait** while it analyzes the video
4. **Review** detected highlights with preview thumbnails
5. **Download** the clips you want — or convert them to TikTok vertical format

Downloaded VODs are saved to a **library** so you can re-analyze them without re-downloading.

---

## Install & Run

### Windows

1. Download this project: green **"<> Code"** button → **"Download ZIP"**
2. Unzip it, open the folder
3. Double-click **`Auto-Clipper.bat`**

That's it. First time it installs everything (Python required — it'll tell you if you need it). Every time after, just double-click the same file.

### Mac

1. Download this project: green **"<> Code"** button → **"Download ZIP"**
2. Double-click the ZIP to unzip it
3. Open the folder and double-click **`Auto-Clipper.command`**

That's it. First time it installs Homebrew, Python, FFmpeg, and all dependencies automatically. It will ask for your Mac password once (you won't see characters as you type — that's normal). Every time after, just double-click the same file.

> **Mac security note:** If macOS says the file "can't be opened", right-click it → Open → click Open. You only need to do this once.

Your browser opens to **http://localhost:8080** — that's the app.

---

## How to Use Auto-Clipper

Once the app is running and you see it in your browser:

### 1. Select Your Game

At the top of the page you'll see game buttons — **Arc Raiders** and **War Thunder**. Click the one you're playing. This tells the app what to look for (each game has different kill feeds, explosions, UI elements, etc).

Your selection is saved automatically. Next time you open the app, it remembers.

### 2. Paste a Twitch VOD Link

Go to [twitch.tv](https://www.twitch.tv/) and find the VOD you want to clip. Copy the URL from the address bar — it looks something like:

```
https://www.twitch.tv/videos/2720880233
```

Paste it into the input box and click **Analyze** (or press Enter).

### 3. (Optional) Only Analyze Part of the VOD

If the stream is really long (like 5+ hours), you can save time by only analyzing a specific part:

1. Click **"+ Download specific part (faster)"**
2. Type a start time like `1:30:00` (1 hour 30 minutes in)
3. Type an end time like `2:00:00`
4. Now it will only download and analyze that 30-minute section

### 4. Wait for Analysis

The app will:
1. **Download** the VOD from Twitch (progress bar shows %)
2. **Analyze** every frame looking for exciting moments
3. **Extract** highlight clips automatically

This takes a few minutes depending on VOD length. A 1-hour VOD takes roughly 3-5 minutes.

### 5. Review Your Clips

When analysis is done, you'll see a grid of clips with:
- **Thumbnail preview** of each highlight
- **Label** describing what happened (e.g. "Kill / Elimination", "Explosion / Combat")
- **Timestamp** showing where in the VOD it happened
- **Confidence bar** showing how sure the detector is

### 6. Preview and Trim

Click any clip to open a preview player. From here you can:

- **Watch** the clip to see if it's actually good
- **Trim** it — use the -5s / -1s / +1s / +5s buttons to adjust the start and end points, then click **Re-cut Clip**
- **Download** the clip
- **Make TikTok** — convert it to vertical 9:16 format (see below)

### 7. TikTok / Vertical Video

Click **Make TikTok** to open the TikTok editor:

1. Pick a **preset layout** — most common is "Cam: Top-Right" which puts gameplay on top (70%) and webcam on bottom (30%)
2. If you don't have a webcam, click **No Webcam** for full-screen gameplay
3. For custom layouts, click **Custom** and drag on the frame to draw your own gameplay and webcam regions
4. Check the **Preview** on the right to see how it'll look
5. Click **Export TikTok Video** — it'll process and auto-download the vertical clip

### 8. Delete Clips You Don't Want

Click **Remove** on any clip card to delete it. This just removes it from the current session — it doesn't affect your Twitch VOD.

---

## iPhone / iPad

The app runs on your computer — you just view it on your phone through Safari.

1. Get Auto-Clipper running on your computer first (see above)
2. Find your computer's IP: on Mac run `ipconfig getifaddr en0` in Terminal, on Windows run `ipconfig` and look for "IPv4 Address" — it's something like `192.168.1.42`
3. On your iPhone (same Wi-Fi), open Safari and go to `http://YOUR_IP:8080`
4. Optional: tap Share → "Add to Home Screen" to save it as an app icon

---

## Supported Games

| Game | What It Detects |
|------|----------------|
| **Arc Raiders** | Kill feed text, damage indicators (red vignette), hit markers (crosshair flash), explosions / muzzle flash, Arc enemy glow (blue), combat chaos |
| **War Thunder** | "Target Destroyed" messages, critical hits, bomb / rocket hits, vehicle fires, explosions, air combat, damage indicators |

Each game has its own detection profile tuned for that game's specific colors, UI layout, and visual effects. Adding a new game is just adding a new profile — the detection engine is the same.

---

## Optional: AI-Powered Analysis

By default Auto-Clipper uses computer vision (color detection + motion analysis) to find highlights. It works without any accounts or API keys.

For smarter detection that actually **understands** what's happening in the gameplay:

1. Click **"+ AI Mode (xAI Grok Vision)"** in the app
2. Get a free API key from [x.ai](https://x.ai/)
3. Paste your key into the field

The AI knows the difference between "walking around doing nothing" and "intense firefight with a kill" — computer vision only sees colors and motion. AI mode finds better clips but uses API credits.

Your API key is saved in the app so you only enter it once.

---

## Troubleshooting

**"python is not recognized" (Windows)**
You didn't check "Add python.exe to PATH" during installation. Uninstall Python, download it again, and this time **check that box** at the bottom of the very first installer screen.

**"git is not recognized" (Windows)**
Close your Command Prompt and open a new one. If it still doesn't work, reinstall Git from [git-scm.com](https://git-scm.com/download/win).

**"ffmpeg is not recognized"**
Run `install.bat` (Windows) or `./install.sh` (Mac) again — it will install FFmpeg for you automatically.

**"brew: command not found" (Mac)**
Run `./install.sh` again — it will install Homebrew for you.

**The installer says it worked but `run.bat` doesn't do anything**
Open Command Prompt manually and type:
```
cd Auto-clipper
venv\Scripts\activate
python app.py
```
This will show you any error messages.

**Clips won't download from Twitch**
Make sure the VOD is **public** (not subscriber-only or deleted). Some streamers delete their VODs after a few days.

**Can't connect from iPhone**
- Are both devices on the **same Wi-Fi network**?
- Is Auto-Clipper actually running on your computer? (You need to keep `run.bat` / `run.sh` open)
- Try turning off VPN on both devices
- Windows: Your firewall might be blocking port 8080 — try temporarily disabling it

**Port 8080 already in use**
Something else is using that port. Close other apps, or edit `app.py` and change `port=8080` to `port=8081` (then use `http://localhost:8081` in your browser).

**Analysis found clips but they're all boring / nothing happening**
Try using AI mode — computer vision sometimes picks up false positives. AI mode is much better at understanding what's actually exciting.

**Analysis takes forever**
Use the "Download specific part" option to only analyze a portion of the VOD instead of the whole thing. A 30-minute section analyzes much faster than a 5-hour stream.
