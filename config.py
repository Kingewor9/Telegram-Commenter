# Telegram API credentials (load from .env in main.py)
API_ID = None
API_HASH = None

# Channels you want to monitor
CHANNELS = ["tiktokleadsgen", "stockverified"]

# Behaviour controls
MODE = "RANDOM"   # or "AI"
DELAY_RANGE = (15, 60)
SKIP_PROBABILITY = 0.3
LOG_ONLY = False   # For posting on comments, I'll change to True if I want logs print only
# Reply queue settings: how long to keep trying to find the discussion message (seconds)
# Increased to 300s to allow the discussion message to appear and conversion to threaded reply
REPLY_QUEUE_MAX_WAIT = 300
# Poll interval for queued jobs (seconds)
REPLY_QUEUE_POLL_INTERVAL = 3
# Local cooldown per linked discussion to avoid flood limits (seconds)
COOLDOWN = 300
