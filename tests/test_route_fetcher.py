import pytest
from unittest.mock import MagicMock
from datetime import datetime
import pytz
import requests
from typing import Tuple, Dict, Any, Optional
from pytest_mock import MockerFixture
from pytest import CaptureFixture

# Assuming the project structure places src/route_fetcher.py relative to tests/
# Adjust the import path if your structure is different
from src.route_fetcher import RouteFetcher
from src.data_models import RouteData

# Define some test coordinates
TEST_ORIGIN: Tuple[float, float] = (48.391598, 10.045831)
TEST_DEST: Tuple[float, float] = (47.972166, 11.720404)

# Define a mock successful API response structure
MOCK_SUCCESS_RESPONSE_JSON: Dict[str, Any] = {
    "destination_addresses": ["Destination Address"],
    "origin_addresses": ["Origin Address"],
    "rows": [
        {
            "elements": [
                {
                    "distance": {"text": "10.0 km", "value": 10000},
                    "duration": {"text": "10 mins", "value": 600},
                    "status": "OK"
                }
            ]
        }
    ],
    "status": "OK"
}

@pytest.fixture
def route_fetcher(mocker: MockerFixture) -> RouteFetcher:
    """Fixture to provide a RouteFetcher instance with mocked API key."""
    # Mock the environment variable for the API key
    mocker.patch('src.route_fetcher.API_KEY', 'fake_api_key')
    return RouteFetcher()

@pytest.fixture
def mock_requests_get(mocker: MockerFixture) -> MagicMock:
    """Fixture to mock requests.get."""
    return mocker.patch('requests.get')

@pytest.fixture
def mock_datetime_now(mocker: MockerFixture) -> MagicMock:
    """Fixture to mock datetime.now to return a fixed time."""
    fixed_time: datetime = datetime(2023, 10, 27, 10, 0, 0, tzinfo=pytz.timezone("Europe/Berlin"))
    # mock_dt_module is a mock of the 'datetime' module as used in 'src.route_fetcher'
    mock_dt_module: MagicMock = mocker.patch('src.route_fetcher.datetime')
    mock_dt_module.now.return_value = fixed_time
    return mock_dt_module # The test function receives the mock of the datetime module

def test_get_current_route_data_success(route_fetcher: RouteFetcher, mock_requests_get: MagicMock, mock_datetime_now: MagicMock) -> None:
    """Tests successful API call and RouteData creation."""
    # Configure the mock response
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_SUCCESS_RESPONSE_JSON
    mock_response.raise_for_status.return_value = None # Simulate no HTTP error
    mock_requests_get.return_value = mock_response

    route_data: Optional[RouteData] = route_fetcher.get_current_route_data(TEST_ORIGIN, TEST_DEST)

    assert route_data is not None # For type narrowing
    assert isinstance(route_data, RouteData)
    assert route_data.origin_lat == TEST_ORIGIN[0]
    assert route_data.origin_lon == TEST_ORIGIN[1]
    assert route_data.dest_lat == TEST_DEST[0]
    assert route_data.dest_lon == TEST_DEST[1]
    assert route_data.distance_m == 10000
    assert route_data.duration_s == 600
    assert route_data.start_time == datetime(2023, 10, 27, 10, 0, 0, tzinfo=pytz.timezone("Europe/Berlin"))

    # Verify requests.get was called with the correct URL (basic check)
    mock_requests_get.assert_called_once()
    call_url: str = mock_requests_get.call_args[0][0]
    assert str(TEST_ORIGIN[0]) in call_url
    assert str(TEST_DEST[0]) in call_url
    assert 'fake_api_key' in call_url

def test_get_current_route_data_api_status_not_ok(route_fetcher: RouteFetcher, mock_requests_get: MagicMock, capsys: CaptureFixture) -> None:
    """Tests API response where element status is not OK."""
    mock_response_json: Dict[str, Any] = MOCK_SUCCESS_RESPONSE_JSON.copy()
    mock_response_json["rows"][0]["elements"][0]["status"] = "ZERO_RESULTS"

    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_json
    mock_requests_get.return_value = mock_response

    route_data: Optional[RouteData] = route_fetcher.get_current_route_data(TEST_ORIGIN, TEST_DEST)

    assert route_data is None
    captured: Any = capsys.readouterr() # CaptureResult is not directly importable from pytest in a simple way for type hints
    assert "Error: Could not retrieve route information. Status: ZERO_RESULTS" in captured.out

def test_get_current_route_data_http_error(route_fetcher: RouteFetcher, mock_requests_get: MagicMock, capsys: CaptureFixture) -> None:
    """Tests handling of HTTP errors from the API."""
    mock_response: MagicMock = MagicMock()
    mock_response.status_code = 403 # Forbidden
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Forbidden")
    mock_requests_get.return_value = mock_response

    route_data: Optional[RouteData] = route_fetcher.get_current_route_data(TEST_ORIGIN, TEST_DEST)

    assert route_data is None
    captured: Any = capsys.readouterr() # CaptureResult is not directly importable
    assert "Error: API request failed. Forbidden" in captured.out
    mock_response.raise_for_status.assert_called_once()

# Add more tests for other error cases: network error, empty rows/elements, unexpected JSON structure, missing API key