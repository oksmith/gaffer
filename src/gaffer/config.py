from pathlib import Path

# FPL API configuration
BASE_URL = "https://fantasy.premierleague.com/api/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"  # use a real user agent
REQUEST_TIMEOUT = 20.0  # seconds

# Retry behaviour (applied per-request inside FPLClient)
MAX_RETRIES = 4
BACKOFF_BASE = 2.0  # seconds; first retry waits ~2s, then 4s, 8s, ...
BACKOFF_CAP = 30.0  # seconds; ceiling for exponential backoff
RETRY_AFTER_CAP = 60.0  # seconds; ignore absurd Retry-After values

# A polite gap between requests (?) - experiment with this if I get rate-limited often
REQUEST_DELAY = 0.0

# Where we store all the data
DATA_DIR = Path(__file__).resolve().parents[2] / "data"  # repo-root/data
