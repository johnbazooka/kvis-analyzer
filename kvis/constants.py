import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
ANALYSIS_DIR = DATA_DIR / "analysis"
AUDIO_DIR = DATA_DIR / "audio"
KEYFRAMES_DIR = DATA_DIR / "keyframes"
COMMENTS_DIR = DATA_DIR / "comments"
CHECKPOINT_FILE = DATA_DIR / "checkpoint.json"
CACHE_DIR = DATA_DIR / "cache"
CONNECTIONS_FILE = ANALYSIS_DIR / "kvis_connections.json"
CHANNEL_CACHE_FILE = CACHE_DIR / "channel_cache.json"

for d in [TRANSCRIPTS_DIR, ANALYSIS_DIR, AUDIO_DIR, CACHE_DIR, KEYFRAMES_DIR, COMMENTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
