"""
Standalone desktop launcher for Arc Raiders Auto-Clipper.
Opens the app in a native window instead of a browser tab.
"""
import sys
import threading
import time
import urllib.request
import urllib.error


def _wait_for_server(host, port, timeout=60):
    """Poll the server until it responds or timeout is reached."""
    url = f"http://{host}:{port}/api/games"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return  # Server is ready
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    print("Warning: server did not respond within timeout, opening anyway...")


def main():
    # Start Flask in a background thread
    from app import app

    server_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=8080, debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()

    # Wait for server to actually be ready (up to 60 seconds)
    _wait_for_server("127.0.0.1", 8080, timeout=60)

    try:
        import webview
        # Open in a native OS window
        webview.create_window(
            "Arc Raiders Auto-Clipper",
            "http://127.0.0.1:8080",
            width=1100,
            height=800,
            min_size=(800, 600),
        )
        webview.start()
    except ImportError:
        # pywebview not installed, fall back to browser
        import webbrowser
        print("pywebview not installed - opening in browser instead.")
        print("To get a native window, run: pip install pywebview")
        print("")
        print("App running at http://localhost:8080")
        webbrowser.open("http://localhost:8080")

        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    main()
