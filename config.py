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
