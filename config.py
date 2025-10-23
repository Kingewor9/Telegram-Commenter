# Telegram API credentials (load from .env in main.py)
API_ID = None
API_HASH = None

# Channels you want to monitor
CHANNELS = ["tiktokleadsgen", "stockverified", "Troll_Football_Telegram", "Manchester_Utdfc", "cristiano", "messimedia", "Uefa_Champions_Leagueee", "liverpool_worldwide", "footballfactlys", "bayern_munich", "premier_league_football_news", "Sky_Sportz_football", "goal_sport_football", "juventus", "Paris_Saint_Germaiin", "jfball", "manchester", "manchesterunited", "tottenhm", "goal264", "Fantasy_Epl"]

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
# How many recent messages to scan when searching for the discussion message
REPLY_QUEUE_SEARCH_LIMIT = 1000
# If True, allow reply jobs to be queued even when the server requests a wait longer
# than REPLY_QUEUE_MAX_WAIT. Use with caution — this can cause jobs to sit for long periods.
REPLY_QUEUE_ALLOW_LONG_WAIT = False
# When allowing long waits, add this slack (seconds) after the required wait before giving up
REPLY_QUEUE_LONG_WAIT_SLACK = 60
# When True, dump a compact debug view of recent messages for a discussion when mapping fails
DEBUG_DUMP_RECENT = True
