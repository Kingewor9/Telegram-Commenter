import os
import threading
import time
import signal
from dotenv import load_dotenv
from flask import Flask, jsonify
import asyncio

# Load env vars
load_dotenv()

# Import app-specific modules lazily (so Flask can import without starting the worker in some contexts)
from telethon import TelegramClient
from telethon.sessions import StringSession
import config as cfg
from modules.listener import register_handlers

app = Flask(__name__)
worker_thread = None
stop_event = threading.Event()
client = None

PORT = int(os.environ.get("PORT", 5000))


def start_telethon_loop():
    """Run the Telethon client in an asyncio loop inside this thread."""
    global client
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    cfg.API_ID = int(os.getenv("API_ID") or 0)
    cfg.API_HASH = os.getenv("API_HASH") or ""

    # Prefer a string session provided via env var (safe to store as secret), else fall back to a named session file
    string_session = os.getenv("TELEGRAM_STRING_SESSION")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if string_session:
        session_obj = StringSession(string_session)
    else:
        session_obj = os.getenv("TELEGRAM_SESSION_NAME", "session_name")

    client = TelegramClient(session_obj, cfg.API_ID, cfg.API_HASH)

    async def runner():
        # Start with a bot token if provided (avoids interactive phone prompt)
        if bot_token:
            print("Starting Telethon with bot token")
            await client.start(bot_token=bot_token)
        else:
            # If a string session was provided we can start non-interactively
            if string_session:
                print("Starting Telethon with TELEGRAM_STRING_SESSION")
                await client.start()
            else:
                # If no string session and no bot token, make sure a local session file exists
                # to avoid Telethon prompting for phone input on a headless host.
                import pathlib
                sess_name = session_obj if isinstance(session_obj, str) else None
                if sess_name:
                    session_file = pathlib.Path(f"{sess_name}.session")
                    if not session_file.exists():
                        print("ERROR: No TELEGRAM_STRING_SESSION or TELEGRAM_BOT_TOKEN set and session file not found.")
                        print("On headless hosts Telethon would prompt for a phone number (interactive) which fails.")
                        print("Please provide a TELEGRAM_STRING_SESSION or TELEGRAM_BOT_TOKEN as an environment variable.")
                        return
                print("Starting Telethon with local session file")
                await client.start()
        register_handlers(client, cfg)
        print("Telethon client started in background worker")
        # run until explicitly disconnected
        await client.run_until_disconnected()

    try:
        loop.run_until_complete(runner())
    except Exception as e:
        print("Telethon worker stopped with error:", e)
    finally:
        try:
            loop.run_until_complete(client.disconnect())
        except Exception:
            pass
        loop.close()


def start_worker():
    global worker_thread
    if worker_thread and worker_thread.is_alive():
        print("Worker already running")
        return

    stop_event.clear()
    worker_thread = threading.Thread(target=start_telethon_loop, daemon=True)
    worker_thread.start()
    print("Background worker thread started")


# Some Flask builds (or Flask 3.x) may not have before_first_request available on the app
# Start the worker lazily when health is called so hosting platforms trigger it reliably.


# Attach SIGTERM handler is done after the handler function is defined below


@app.route("/health")
def health():
    """Simple health endpoint so Render thinks this is a web service."""
    # Start the worker on first health check if it's not already running. This avoids
    # using `before_first_request`, which may not exist depending on the Flask build.
    if not (worker_thread and worker_thread.is_alive()):
        print("Health endpoint: worker not running, starting worker")
        start_worker()

    status = {
        "worker_running": bool(worker_thread and worker_thread.is_alive()),
        "port": PORT,
    }
    return jsonify(status)


@app.route("/")
def index():
    """Root endpoint: keep simple and start worker so platform checks that hit `/` will trigger the worker."""
    if not (worker_thread and worker_thread.is_alive()):
        print("Root endpoint: worker not running, starting worker")
        start_worker()

    return jsonify({"status": "ok", "worker_running": bool(worker_thread and worker_thread.is_alive())})


@app.route("/start-worker", methods=["POST"])
def start_worker_endpoint():
    """Optional endpoint to start the worker if you don't want it to auto-start."""
    start_worker()
    return jsonify({"started": True})


def handle_sigterm(*_):
    """Graceful shutdown when platform sends SIGTERM."""
    print("SIGTERM received, shutting down background worker")
    try:
        if client:
            asyncio.get_event_loop().run_until_complete(client.disconnect())
    except Exception:
        pass
    stop_event.set()


try:
    signal.signal(signal.SIGTERM, handle_sigterm)
except Exception:
    pass


if __name__ == "__main__":
    # Auto-start worker when running locally for convenience
    start_worker()
    app.run(host="0.0.0.0", port=PORT)