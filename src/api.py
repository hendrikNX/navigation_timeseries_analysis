from flask import Flask, request, jsonify
from datetime import datetime
# import sqlite3 # No longer needed directly here

# Assuming src is in PYTHONPATH or running from project root
try:
    from .storage.sqlite_storage import SQLiteStorage
    from .storage.csv_storage import CsvStorage
    from .data_models import RouteData
    from .config import SQLITE_DB_PATH, CSV_FILE_PATH, STORAGE_TYPE, DATA_DIR
    from .storage.base import DeleteParams
except ImportError:
    # Fallback for simpler execution context (e.g. direct run of api.py for testing)
    from storage.sqlite_storage import SQLiteStorage
    from storage.csv_storage import CsvStorage
    from data_models import RouteData
    from config import SQLITE_DB_PATH, CSV_FILE_PATH, STORAGE_TYPE, DATA_DIR
    from storage.base import DeleteParams

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

@app.route('/api/routes', methods=['DELETE'])
def delete_route_data():
    delete_kwargs: DeleteParams = {} # Using TypedDict for clarity, will be a normal dict at runtime
    raw_params = {}

    # Collect all potential delete parameters from query string
    if 'id' in request.args:
        raw_params['id'] = request.args.get('id')
    if 'time' in request.args:
        raw_params['time'] = request.args.get('time')
    
    # Check for time_range parameters
    has_start_time = 'start_time' in request.args
    has_end_time = 'end_time' in request.args
    if has_start_time and has_end_time:
        raw_params['time_range'] = (request.args.get('start_time'), request.args.get('end_time'))
    elif has_start_time or has_end_time:
        # If only one of start_time/end_time is provided, it's an error
        return jsonify({"error": "Both start_time and end_time are required for a time_range filter."}), 400

    # Ensure exactly one deletion criterion is provided
    if len(raw_params) == 0:
        return jsonify({"error": "No deletion criteria provided. Use 'id', 'time', or 'start_time' & 'end_time'."}), 400
    if len(raw_params) > 1:
        return jsonify({"error": f"Multiple deletion criteria provided ({', '.join(raw_params.keys())}). Please use only one type of criterion."}), 400

    criterion_key = list(raw_params.keys())[0]
    criterion_value = raw_params[criterion_key]

    try:
        if criterion_key == 'id':
            id_str = str(criterion_value) # Ensure it's a string before splitting
            if ',' in id_str:
                delete_kwargs['id'] = [int(i.strip()) for i in id_str.split(',') if i.strip()]
                if not delete_kwargs['id']: raise ValueError("ID list cannot be empty if commas are present.")
            else:
                delete_kwargs['id'] = int(id_str)
        
        elif criterion_key == 'time':
            time_str = str(criterion_value) # Ensure it's a string
            parsed_times = []
            if ',' in time_str:
                parsed_times = [datetime.fromisoformat(t.strip()) for t in time_str.split(',') if t.strip()]
                if not parsed_times: raise ValueError("Time list cannot be empty if commas are present.")
            else:
                parsed_times = [datetime.fromisoformat(time_str)]
            
            for t_obj in parsed_times:
                if t_obj.tzinfo is None or t_obj.tzinfo.utcoffset(t_obj) is None:
                    raise ValueError("All 'time' values must be timezone-aware ISO strings.")
            delete_kwargs['time'] = parsed_times if len(parsed_times) > 1 else parsed_times[0]

        elif criterion_key == 'time_range':
            start_time_str, end_time_str = criterion_value
            start_dt = datetime.fromisoformat(start_time_str)
            end_dt = datetime.fromisoformat(end_time_str)
            if start_dt.tzinfo is None or start_dt.tzinfo.utcoffset(start_dt) is None or \
               end_dt.tzinfo is None or end_dt.tzinfo.utcoffset(end_dt) is None:
                raise ValueError("start_time and end_time for time_range must be timezone-aware ISO strings.")
            if start_dt >= end_dt: # This check is also in storage, but good to have early
                raise ValueError("start_time must be before end_time for time_range.")
            delete_kwargs['time_range'] = (start_dt, end_dt)

    except ValueError as e:
        app.logger.error(f"Invalid parameter format for deletion: {e}. Params: {raw_params}")
        return jsonify({"error": f"Invalid parameter format: {e}"}), 400
    
    try:
        storage.delete(**delete_kwargs) # Unpack the dict to keyword arguments
        # The storage methods already print the count of deleted rows to their logs.
        return jsonify({"message": f"Deletion process initiated with criteria: {criterion_key}. Check server logs for details."}), 200
    except ValueError as e: # Catch errors from storage.delete (e.g., specific validation errors)
        app.logger.error(f"Error during storage deletion: {e}. Delete kwargs: {delete_kwargs}")
        return jsonify({"error": str(e)}), 400 
    except Exception as e:
        app.logger.error(f"An internal error occurred during deletion: {e}. Delete kwargs: {delete_kwargs}")
        return jsonify({"error": "An internal error occurred during deletion"}), 500

if __name__ == '__main__':
    # This is for local development. For Docker, use `flask run` or a WSGI server.
    # Storage initialization messages are now printed above.
    app.logger.info(f"Data directory is: {DATA_DIR}")
    app.run(host='0.0.0.0', port=5000, debug=True)