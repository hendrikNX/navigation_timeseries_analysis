import os
from dotenv import load_dotenv
from typing import Tuple, Optional

# Load environment variables from .env file
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))

API_KEY_GOOGLE_MAPS_PLATFORM = os.environ.get("API_KEY_GOOGLE_MAPS_PLATFORM")

# --- Scheduler settings ---
# How many times per hour to fetch data
FETCH_FREQUENCY_PER_HOUR: int = 4  # e.g., 4 times per hour means every 15 minutes

# On which weekdays to fetch data
WEEKDAYS: list[int] = [0, 1, 2, 3, 4] # 0-6 for Monday-Sunday

# In which time frames to fetch data
START_TIME_ROUTE_TO_DEST: int = 6 # e.g., start at 6:00 for the route to the destination
END_TIME_ROUTE_TO_DEST: int = 12
START_TIME_ROUTE_TO_ORIGIN: int = 14 # e.g., start at 14:00 for the route back to the origin
END_TIME_ROUTE_TO_ORIGIN: int = 20

# --- Route settings ---
# Default coordinates (used if environment variables are not set)
DEFAULT_ORIGIN_LAT = 48.115581
DEFAULT_ORIGIN_LON = 11.653591
DEFAULT_DEST_LAT = 48.193418
DEFAULT_DEST_LON = 11.552552

def get_coords_from_env(env_var_name: str, default_lat: float, default_lon: float) -> Tuple[float, float]:
    """Helper function to get coordinates from environment or use defaults."""
    coords_str = os.environ.get(env_var_name)
    if coords_str:
        try:
            lat_str, lon_str = coords_str.split(',')
            return (float(lat_str.strip()), float(lon_str.strip()))
        except ValueError:
            print(f"Warning: Invalid format for {env_var_name} in .env. Expected 'lat,lon'. Using default.")
    return (default_lat, default_lon)

ORIGIN_COORDS: Tuple[float, float] = get_coords_from_env("ORIGIN_COORDS_LATLON", DEFAULT_ORIGIN_LAT, DEFAULT_ORIGIN_LON)
DEST_COORDS: Tuple[float, float] = get_coords_from_env("DEST_COORDS_LATLON", DEFAULT_DEST_LAT, DEFAULT_DEST_LON)

# Storage settings
STORAGE_TYPE: str = os.environ.get("STORAGE_TYPE", "csv").lower()

# Determine the data directory: use APP_DATA_DIR from env if running in Docker,
# otherwise default to a 'data' folder in the project root.
APP_DATA_DIR_ENV: Optional[str] = os.environ.get("APP_DATA_DIR")
DATA_DIR: str = APP_DATA_DIR_ENV if APP_DATA_DIR_ENV else os.path.join(project_root, "data")
CSV_FILE_PATH: str = os.path.join(DATA_DIR, "routes_data.csv")
SQLITE_DB_PATH: str = os.path.join(DATA_DIR, "routes_data.db")

# API settings
API_BASE_URL: str = os.environ.get("API_BASE_URL", "http://localhost:5000") # Base URL for the API service

# Ensure data directory exists
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

if not API_KEY_GOOGLE_MAPS_PLATFORM:
    raise ValueError("API_KEY_GOOGLE_MAPS_PLATFORM not found. Please set it in .env or environment variables.")