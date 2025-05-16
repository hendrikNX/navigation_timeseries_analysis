import pytest
from unittest.mock import MagicMock, call
from typing import Tuple, Optional
from datetime import datetime
import pytz
from pytest_mock import MockerFixture
from pytest import CaptureFixture

from src.scheduler import JobScheduler
from src.route_fetcher import RouteFetcher
from src.storage.base import DataStorage
from src.data_models import RouteData

# Test constants
TEST_ORIGIN_COORDS: Tuple[float, float] = (10.0, 20.0)
TEST_DEST_COORDS: Tuple[float, float] = (30.0, 40.0)
TEST_INTERVAL_SECONDS: int = 5 # Use a short interval for testing

@pytest.fixture
def mock_route_fetcher(mocker: MockerFixture) -> MagicMock:
    """Mocks the RouteFetcher."""
    mock = mocker.MagicMock(spec=RouteFetcher)
    # Ensure get_current_route_data is a MagicMock itself to allow further configuration
    mock.get_current_route_data = mocker.MagicMock()
    return mock

@pytest.fixture
def mock_data_storage(mocker: MockerFixture) -> MagicMock:
    """Mocks the DataStorage."""
    mock = mocker.MagicMock(spec=DataStorage)
    mock.save = mocker.MagicMock()
    return mock

@pytest.fixture
def sample_route_data() -> RouteData:
    """Provides a sample RouteData object."""
    return RouteData(
        origin_lat=TEST_ORIGIN_COORDS[0],
        origin_lon=TEST_ORIGIN_COORDS[1],
        dest_lat=TEST_DEST_COORDS[0],
        dest_lon=TEST_DEST_COORDS[1],
        distance_m=5000,
        duration_s=300,
        duration_in_traffic_s=250,
        start_time=datetime.now(tz=pytz.timezone("Europe/Berlin"))
    )

@pytest.fixture
def scheduler(mock_route_fetcher: MagicMock, mock_data_storage: MagicMock) -> JobScheduler:
    """Provides a JobScheduler instance with mocked dependencies."""
    return JobScheduler(
        route_fetcher=mock_route_fetcher,
        data_storage=mock_data_storage,
        origin_coords=TEST_ORIGIN_COORDS,
        dest_coords=TEST_DEST_COORDS,
        interval_seconds=TEST_INTERVAL_SECONDS
    )

def test_scheduler_run_fetches_and_saves_data(
    scheduler: JobScheduler,
    mock_route_fetcher: MagicMock,
    mock_data_storage: MagicMock,
    sample_route_data: RouteData,
    mocker: MockerFixture,
    capsys: CaptureFixture
):
    """Tests a single successful run of fetching and saving data."""
    mock_route_fetcher.get_current_route_data.return_value = sample_route_data
    mock_time_sleep = mocker.patch('time.sleep', side_effect=InterruptedError) # Stop after one loop

    with pytest.raises(InterruptedError): # Expect the loop to be broken by our mock_time_sleep
        scheduler.run()

    mock_route_fetcher.get_current_route_data.assert_called_once_with(
        origin_cords=TEST_ORIGIN_COORDS,
        dest_cords=TEST_DEST_COORDS
    )
    mock_data_storage.save.assert_called_once_with(sample_route_data)
    mock_time_sleep.assert_called_once_with(TEST_INTERVAL_SECONDS)

    captured = capsys.readouterr()
    assert "Fetching route data..." in captured.out
    assert "Data processed and saved." in captured.out
    assert f"Waiting for {TEST_INTERVAL_SECONDS} seconds" in captured.out

def test_scheduler_run_handles_no_data_fetched(
    scheduler: JobScheduler,
    mock_route_fetcher: MagicMock,
    mock_data_storage: MagicMock,
    mocker: MockerFixture,
    capsys: CaptureFixture
):
    """Tests the case where route fetcher returns None."""
    mock_route_fetcher.get_current_route_data.return_value = None
    mock_time_sleep = mocker.patch('time.sleep', side_effect=InterruptedError)

    with pytest.raises(InterruptedError):
        scheduler.run()

    mock_route_fetcher.get_current_route_data.assert_called_once()
    mock_data_storage.save.assert_not_called()
    mock_time_sleep.assert_called_once_with(TEST_INTERVAL_SECONDS)

    captured = capsys.readouterr()
    assert "No data fetched or an error occurred during fetch." in captured.out

def test_scheduler_run_handles_exception_during_fetch(
    scheduler: JobScheduler,
    mock_route_fetcher: MagicMock,
    mock_data_storage: MagicMock,
    mocker: MockerFixture,
    capsys: CaptureFixture
):
    """Tests handling of an exception raised by route_fetcher."""
    test_exception = ValueError("API Error")
    mock_route_fetcher.get_current_route_data.side_effect = test_exception
    mock_time_sleep = mocker.patch('time.sleep', side_effect=InterruptedError)

    with pytest.raises(InterruptedError):
        scheduler.run()

    mock_route_fetcher.get_current_route_data.assert_called_once()
    mock_data_storage.save.assert_not_called()
    mock_time_sleep.assert_called_once_with(TEST_INTERVAL_SECONDS)

    captured = capsys.readouterr()
    assert f"An error occurred in the scheduler loop: {test_exception}" in captured.out

def test_scheduler_run_multiple_loops(scheduler: JobScheduler, mock_route_fetcher: MagicMock, mock_data_storage: MagicMock, sample_route_data: RouteData, mocker: MockerFixture):
    """Tests that the scheduler loops multiple times."""
    mock_route_fetcher.get_current_route_data.return_value = sample_route_data

    # Let time.sleep be called twice, then raise an error to stop the test
    mock_time_sleep = mocker.patch('time.sleep', side_effect=[None, InterruptedError])

    with pytest.raises(InterruptedError):
        scheduler.run()

    assert mock_route_fetcher.get_current_route_data.call_count == 2
    assert mock_data_storage.save.call_count == 2
    assert mock_time_sleep.call_count == 2
    mock_time_sleep.assert_has_calls([call(TEST_INTERVAL_SECONDS), call(TEST_INTERVAL_SECONDS)])