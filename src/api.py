from flask import Flask, request, jsonify
from datetime import datetime
# import sqlite3 # No longer needed directly here

# Assuming src is in PYTHONPATH or running from project root
try:
    from .storage.sqlite_storage import SQLiteStorage
    from .storage.csv_storage import CsvStorage
    from .data_models import RouteData
    from .config import SQLITE_DB_PATH, CSV_FILE_PATH, STORAGE_TYPE, DATA_DIR # DATA_DIR for Docker volume mapping reference
except ImportError:
    # Fallback for simpler execution context (e.g. direct run of api.py for testing)
    from storage.sqlite_storage import SQLiteStorage
    from storage.csv_storage import CsvStorage
    from data_models import RouteData
    from config import SQLITE_DB_PATH, CSV_FILE_PATH, STORAGE_TYPE, DATA_DIR

app = Flask(__name__)

# Initialize storage based on configuration
if STORAGE_TYPE == "sqlite":
    storage = SQLiteStorage(db_path=SQLITE_DB_PATH)
    app.logger.info(f"Using SQLite storage: {SQLITE_DB_PATH}")
elif STORAGE_TYPE == "csv":
    storage = CsvStorage(file_path=CSV_FILE_PATH)
    app.logger.info(f"Using CSV storage: {CSV_FILE_PATH}")
else:
    # Default to SQLite if an unsupported type is specified
    app.logger.error(f"Unsupported STORAGE_TYPE: {STORAGE_TYPE}. Defaulting to SQLite.")
    storage = SQLiteStorage(db_path=SQLITE_DB_PATH)

@app.route('/api/routes', methods=['POST'])
def add_route_data():
    if not request.is_json:
        return jsonify({"error": "Invalid input, JSON payload expected"}), 400

    data = request.get_json()
    required_fields = ["origin_lat", "origin_lon", "dest_lat", "dest_lon",
                       "distance_m", "duration_s", "duration_in_traffic_s", "start_time"]

    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    try:
        # Convert start_time from ISO string to datetime object.
        # datetime.fromisoformat() handles timezone-aware ISO strings correctly.
        start_time_dt = datetime.fromisoformat(data["start_time"])

        route_data_obj = RouteData(
            origin_lat=float(data["origin_lat"]),
            origin_lon=float(data["origin_lon"]),
            dest_lat=float(data["dest_lat"]),
            dest_lon=float(data["dest_lon"]),
            distance_m=int(data["distance_m"]),
            duration_s=int(data["duration_s"]),
            duration_in_traffic_s=int(data["duration_in_traffic_s"]),
            start_time=start_time_dt
        )
        storage.save(route_data_obj)
        return jsonify({"message": "Route data added successfully"}), 201

    except ValueError as e:
        app.logger.error(f"Invalid data format: {e}. Payload: {data}")
        return jsonify({"error": f"Invalid data format: {e}"}), 400
    except Exception as e:
        app.logger.error(f"An internal error occurred: {e}. Payload: {data}")
        return jsonify({"error": "An internal error occurred"}), 500

@app.route('/api/routes', methods=['GET'])
def get_route_data():
    try:
        limit = request.args.get('limit', default=100, type=int) # Default to 100, adjust as needed
        if limit <= 0 or limit > 1000: # Add a reasonable upper bound
            limit = 100

        data = storage.load(limit=limit)
        return jsonify(data), 200
    except Exception as e:
        app.logger.error(f"Error fetching data: {e}")
        return jsonify({"error": "An internal error occurred while fetching data"}), 500

if __name__ == '__main__':
    # This is for local development. For Docker, use `flask run` or a WSGI server.
    # Storage initialization messages are now printed above.
    app.logger.info(f"Data directory is: {DATA_DIR}")
    app.run(host='0.0.0.0', port=5000, debug=True)