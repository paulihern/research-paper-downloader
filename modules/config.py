import os
from pathlib import Path

# Base data folder
BASE_PATH = Path.home() / "Desktop" / "RA"
BASE_PATH.mkdir(parents=True, exist_ok=True)
# Paths to JSON data files
PROFESSORS_PATH = BASE_PATH / "professors.json"
# Optional: API key for Semantic Scholar
S2_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "3blxPflYx32MKqbHNfRgh3cqzz69Xh3511dq3NQI")
S2_BASE = "https://api.semanticscholar.org/graph/v1"
# Default departments we support
DEPARTMENTS = {
    "UIUC": "Mechanical Engineering",
    "Northwestern": "Mechanical Engineering"
}
# Control request pacing
MIN_INTERVAL = 1.25  # seconds between API requests
