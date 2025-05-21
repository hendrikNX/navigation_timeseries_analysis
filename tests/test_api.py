import pytest
import json
from datetime import datetime, timezone, timedelta
import sqlite3

# Pytest uses the project root as the current working directory by default if you run it from there.
# Ensure src is in PYTHONPATH or tests are run in a way that src can be found.

@pytest.fixture
def client(mocker, tmp_path):
    """
    Provides a Flask test client configured with a temporary SQLite database.
    """
    test_db_file = tmp_path / "test_api_routes.db"

    # Patch SQLITE_DB_PATH in the src.config module.
    # This needs to happen BEFORE src.api (and its storage instance) is imported/created.
    # The api.py module imports SQLITE_DB_PATH from src.config.
    mocker.patch('src.config.SQLITE_DB_PATH', str(test_db_file))
    mocker.patch('src.api.SQLITE_DB_PATH', str(test_db_file)) # Also patch it directly in api.py's scope if it re-imports

    # Import necessary components.
    # We need to ensure that the 'storage' object used by the API routes
    # is instantiated *after* SQLITE_DB_PATH has been patched.
    import src.api # Import the module to access its members
    from src.storage.sqlite_storage import SQLiteStorage # Import the storage class

    # Explicitly re-initialize the 'storage' object in the 'src.api' module.
    # This ensures it uses the patched SQLITE_DB_PATH.
    src.api.storage = SQLiteStorage(db_path=str(test_db_file))

    app = src.api.app # Get the app object from the now-configured module
    app.config['TESTING'] = True

    with app.test_client() as test_client:
        yield test_client

    # tmp_path is automatically cleaned up by pytest


@pytest.fixture
def sample_payload_valid():
    # Using timezone.utc for consistency, matching test_sqlite_storage.py
    # datetime.fromisoformat() in the API will handle this correctly.
    # The API's RouteData model expects a datetime object.
    # SQLiteStorage.save() converts it back to ISO string.
    return {
        "origin_lat": 52.5200,
        "origin_lon": 13.4050,
        "dest_lat": 48.8566,
        "dest_lon": 2.3522,
        "distance_m": 1050000,
        "duration_s": 36000,
        "duration_in_traffic_s": 37800,
        "start_time": datetime.now(timezone.utc).isoformat() # Dynamic valid ISO string
    }


class TestApiPostRoutes:
    def test_add_route_data_success(self, client, sample_payload_valid, tmp_path):
        response = client.post('/api/routes', json=sample_payload_valid)
        assert response.status_code == 201
        assert response.json == {"message": "Route data added successfully"}

        # Verify data in the database
        db_path = tmp_path / "test_api_routes.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM route_times WHERE origin_lat = ?", (sample_payload_valid["origin_lat"],))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row["distance_m"] == sample_payload_valid["distance_m"]
        assert row["start_time"] == sample_payload_valid["start_time"]

    def test_add_route_data_missing_field(self, client, sample_payload_valid):
        payload_missing_field = sample_payload_valid.copy()
        del payload_missing_field["distance_m"]
        response = client.post('/api/routes', json=payload_missing_field)
        assert response.status_code == 400
        assert "Missing field: distance_m" in response.json["error"]

    def test_add_route_data_invalid_json(self, client):
        response = client.post('/api/routes', data="not a json string", content_type="application/json")
        assert response.status_code == 400
        # Flask's default 400 error for malformed JSON in the request body is often HTML/text, not JSON.
        # So, response.json would be None. We check the raw response data.
        assert "request that this server could not understand" in response.data.decode('utf-8')

    def test_add_route_data_not_json_content_type(self, client, sample_payload_valid):
        response = client.post('/api/routes', data=json.dumps(sample_payload_valid), content_type="text/plain")
        assert response.status_code == 400
        assert "Invalid input, JSON payload expected" in response.json["error"]

    def test_add_route_data_invalid_data_type(self, client, sample_payload_valid):
        payload_invalid_type = sample_payload_valid.copy()
        payload_invalid_type["distance_m"] = "not_an_integer"
        response = client.post('/api/routes', json=payload_invalid_type)
        assert response.status_code == 400
        assert "Invalid data format" in response.json["error"]
        assert "invalid literal for int()" in response.json["error"] # Specific error from int()

    def test_add_route_data_invalid_start_time_format(self, client, sample_payload_valid):
        payload_invalid_time = sample_payload_valid.copy()
        payload_invalid_time["start_time"] = "2023-10-26 12:00:00" # Not ISO format
        response = client.post('/api/routes', json=payload_invalid_time)
        assert response.status_code == 400
        assert "Invalid data format" in response.json["error"]
        assert "start_time must be timezone-aware" in response.json["error"] # Specific error from datetime.fromisoformat()


class TestApiGetRoutes:
    def test_get_route_data_empty(self, client):
        response = client.get('/api/routes')
        assert response.status_code == 200
        assert response.json == []

    def test_get_route_data_with_data(self, client, sample_payload_valid, tmp_path):
        # Post some data first
        client.post('/api/routes', json=sample_payload_valid)

        # Create a second distinct entry
        payload2 = sample_payload_valid.copy()
        payload2["origin_lat"] = 50.0
        # Ensure start_time is different for ordering
        dt_obj = datetime.fromisoformat(payload2["start_time"])
        payload2["start_time"] = (dt_obj - timedelta(hours=1)).isoformat()
        client.post('/api/routes', json=payload2)

        response = client.get('/api/routes')
        assert response.status_code == 200
        data = response.json
        assert len(data) == 2
        # Check if ordered by start_time DESC (most recent first)
        assert data[0]["origin_lat"] == sample_payload_valid["origin_lat"] # The one with later start_time
        assert data[1]["origin_lat"] == payload2["origin_lat"]

        assert data[0]["distance_m"] == sample_payload_valid["distance_m"]
        assert data[0]["start_time"] == sample_payload_valid["start_time"]

    def test_get_route_data_with_limit(self, client, sample_payload_valid):
        # Post 3 items
        for i in range(3):
            payload = sample_payload_valid.copy()
            payload["distance_m"] = 10000 + i
            # Ensure start_time is different and decreasing for predictable order
            dt_obj = datetime.fromisoformat(payload["start_time"])
            payload["start_time"] = (dt_obj - timedelta(minutes=i)).isoformat()
            client.post('/api/routes', json=payload)

        response = client.get('/api/routes?limit=2')
        assert response.status_code == 200
        data = response.json
        assert len(data) == 2
        # Data is ordered by start_time DESC.
        # The one with i=0 has the latest start_time.
        assert data[0]["distance_m"] == 10000 + 0
        assert data[1]["distance_m"] == 10000 + 1

    def test_get_route_data_limit_zero(self, client, sample_payload_valid):
        response = client.get('/api/routes?limit=0')
        assert response.status_code == 200
        # API clamps limit to 100 if <=0 or >1000
        # If there's no data, it will be empty. Let's add one item.
        client.post('/api/routes', json=sample_payload_valid)
        response = client.get('/api/routes?limit=0')
        data = response.json
        assert len(data) == 1 # Default limit of 100 is applied, but only 1 item exists

    def test_get_route_data_limit_too_large(self, client, sample_payload_valid):
        response = client.get('/api/routes?limit=2000')
        assert response.status_code == 200
        # API clamps limit to 100 if <=0 or >1000
        client.post('/api/routes', json=sample_payload_valid)
        response = client.get('/api/routes?limit=2000')
        data = response.json
        assert len(data) == 1 # Default limit of 100 is applied, but only 1 item exists

    def test_get_route_data_invalid_limit_type(self, client, sample_payload_valid):
        response = client.get('/api/routes?limit=abc')
        assert response.status_code == 200 # Flask's request.args.get with type=int defaults on error
        # API clamps limit to 100 if type conversion fails for limit
        client.post('/api/routes', json=sample_payload_valid)
        response = client.get('/api/routes?limit=abc')
        data = response.json
        assert len(data) == 1 # Default limit of 100 is applied, but only 1 item exists


class TestApiDeleteRoutes:

    def _get_all_db_records(self, db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM route_times ORDER BY id ASC")
        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return records

    def test_delete_by_single_id_success(self, client, sample_payload_valid, tmp_path):
        # Post two records
        client.post('/api/routes', json=sample_payload_valid) # ID 1
        payload2 = sample_payload_valid.copy()
        payload2["distance_m"] = 100
        client.post('/api/routes', json=payload2) # ID 2

        db_path = tmp_path / "test_api_routes.db"
        assert len(self._get_all_db_records(db_path)) == 2

        response = client.delete('/api/routes?id=1')
        assert response.status_code == 200
        assert "Deletion process initiated" in response.json["message"]

        records = self._get_all_db_records(db_path)
        assert len(records) == 1
        assert records[0]["id"] == 2
        assert records[0]["distance_m"] == 100

    def test_delete_by_list_of_ids_success(self, client, sample_payload_valid, tmp_path):
        client.post('/api/routes', json=sample_payload_valid) # ID 1
        payload2 = sample_payload_valid.copy(); payload2["distance_m"] = 200
        client.post('/api/routes', json=payload2) # ID 2
        payload3 = sample_payload_valid.copy(); payload3["distance_m"] = 300
        client.post('/api/routes', json=payload3) # ID 3

        db_path = tmp_path / "test_api_routes.db"
        assert len(self._get_all_db_records(db_path)) == 3

        response = client.delete('/api/routes?id=1,3')
        assert response.status_code == 200

        records = self._get_all_db_records(db_path)
        assert len(records) == 1
        assert records[0]["id"] == 2
        assert records[0]["distance_m"] == 200

    def test_delete_by_single_time_success(self, client, sample_payload_valid, tmp_path):
        time_base = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        
        payload1 = sample_payload_valid.copy(); payload1["start_time"] = time_base.isoformat(); payload1["distance_m"] = 10
        client.post('/api/routes', json=payload1) # Will be deleted

        payload2 = sample_payload_valid.copy(); payload2["start_time"] = (time_base + timedelta(seconds=30)).isoformat(); payload2["distance_m"] = 20
        client.post('/api/routes', json=payload2) # Will be deleted (same minute)

        payload3 = sample_payload_valid.copy(); payload3["start_time"] = (time_base + timedelta(minutes=5)).isoformat(); payload3["distance_m"] = 30
        client.post('/api/routes', json=payload3) # Should remain

        db_path = tmp_path / "test_api_routes.db"
        assert len(self._get_all_db_records(db_path)) == 3

        # Delete using a time that falls into the first minute
        response = client.delete(f'/api/routes?time={time_base.isoformat().replace("+","%2B")}')
        assert response.status_code == 200

        records = self._get_all_db_records(db_path)
        assert len(records) == 1
        assert records[0]["distance_m"] == 30

    def test_delete_by_time_range_success(self, client, sample_payload_valid, tmp_path):
        time_base = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        payload_before = sample_payload_valid.copy(); payload_before["start_time"] = (time_base - timedelta(minutes=10)).isoformat(); payload_before["distance_m"] = 100
        client.post('/api/routes', json=payload_before) # Should remain

        payload_in = sample_payload_valid.copy(); payload_in["start_time"] = time_base.isoformat(); payload_in["distance_m"] = 200
        client.post('/api/routes', json=payload_in) # Should be deleted

        payload_after = sample_payload_valid.copy(); payload_after["start_time"] = (time_base + timedelta(minutes=10)).isoformat(); payload_after["distance_m"] = 300
        client.post('/api/routes', json=payload_after) # Should remain

        db_path = tmp_path / "test_api_routes.db"
        assert len(self._get_all_db_records(db_path)) == 3

        start_range_iso = (time_base - timedelta(minutes=5)).isoformat()
        end_range_iso = (time_base + timedelta(minutes=5)).isoformat()

        response = client.delete(f'/api/routes?start_time={start_range_iso.replace("+","%2B")}&end_time={end_range_iso.replace("+","%2B")}')
        assert response.status_code == 200

        records = self._get_all_db_records(db_path)
        assert len(records) == 2
        distances = {r["distance_m"] for r in records}
        assert 100 in distances
        assert 300 in distances
        assert 200 not in distances

    def test_delete_no_criteria(self, client):
        response = client.delete('/api/routes')
        assert response.status_code == 400
        assert "No deletion criteria provided" in response.json["error"]

    def test_delete_multiple_criteria(self, client):
        time_now_iso = datetime.now(timezone.utc).isoformat()
        response = client.delete(f'/api/routes?id=1&time={time_now_iso}')
        assert response.status_code == 400
        assert "Multiple deletion criteria provided" in response.json["error"]

    def test_delete_invalid_id_format(self, client):
        response = client.delete('/api/routes?id=abc')
        assert response.status_code == 400
        assert "Invalid parameter format" in response.json["error"]
        assert "invalid literal for int()" in response.json["error"]

    def test_delete_invalid_time_format(self, client):
        response = client.delete('/api/routes?time=not-a-date')
        assert response.status_code == 400
        assert "Invalid parameter format" in response.json["error"]
        assert "Invalid isoformat string" in response.json["error"]

    def test_delete_time_not_timezone_aware(self, client):
        naive_time_iso = datetime.now().isoformat() # Naive datetime
        response = client.delete(f'/api/routes?time={naive_time_iso}')
        assert response.status_code == 400
        assert "Invalid parameter format" in response.json["error"]
        assert "All 'time' values must be timezone-aware" in response.json["error"]

    def test_delete_invalid_time_range_start_after_end(self, client):
        start_time = datetime.now(timezone.utc)
        end_time = start_time - timedelta(hours=1)
        response = client.delete(f'/api/routes?start_time={start_time.isoformat().replace("+","%2B")}&end_time={end_time.isoformat().replace("+","%2B")}')
        assert response.status_code == 400
        assert "Invalid parameter format" in response.json["error"] # This error comes from API layer
        assert "start_time must be before end_time" in response.json["error"]

    def test_delete_time_range_missing_one_part(self, client):
        start_time_iso = datetime.now(timezone.utc).isoformat()
        response = client.delete(f'/api/routes?start_time={start_time_iso}')
        assert response.status_code == 400
        assert "Both start_time and end_time are required" in response.json["error"]

    def test_delete_non_existent_id(self, client, sample_payload_valid, tmp_path):
        client.post('/api/routes', json=sample_payload_valid) # ID 1
        db_path = tmp_path / "test_api_routes.db"
        initial_records_count = len(self._get_all_db_records(db_path))

        response = client.delete('/api/routes?id=999')
        assert response.status_code == 200 # Deleting non-existent is not an API error
        
        assert len(self._get_all_db_records(db_path)) == initial_records_count

    def test_delete_empty_id_list_in_params(self, client, sample_payload_valid, tmp_path):
        # Test ?id= (empty string)
        # The API's parsing `int(id_str)` will raise ValueError for empty string.
        response = client.delete('/api/routes?id=')
        assert response.status_code == 400
        assert "Invalid parameter format" in response.json["error"]

        # Test ?id=,, (list of empty strings)
        # The API's parsing `[int(i.strip()) for i in id_str.split(',') if i.strip()]`
        # will result in an empty list. Then `if not delete_kwargs['id']` check is hit.
        client.post('/api/routes', json=sample_payload_valid) # Add some data
        db_path = tmp_path / "test_api_routes.db"
        initial_records_count = len(self._get_all_db_records(db_path))

        response = client.delete('/api/routes?id=,,')
        assert response.status_code == 400 # API raises ValueError("ID list cannot be empty if commas are present.")
        assert "Invalid parameter format" in response.json["error"]
        assert "ID list cannot be empty" in response.json["error"]

        # Ensure no data was deleted
        assert len(self._get_all_db_records(db_path)) == initial_records_count