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