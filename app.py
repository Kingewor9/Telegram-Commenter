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

    client = TelegramClient(os.getenv("TELEGRAM_SESSION_NAME", "session_name"), cfg.API_ID, cfg.API_HASH)

    async def runner():
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


@app.route("/health")
def health():
    """Simple health endpoint so Render thinks this is a web service."""
    status = {
        "worker_running": bool(worker_thread and worker_thread.is_alive()),
        "port": PORT,
    }
    return jsonify(status)


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


if __name__ == "__main__":
    # Auto-start worker when running locally for convenience
    start_worker()
    app.run(host="0.0.0.0", port=PORT)