import pytest
from unittest.mock import MagicMock # Can also use mocker.MagicMock
from datetime import datetime, timedelta
import pytz
from freezegun import freeze_time
from pytest_mock import MockerFixture

# Attempt to import from src, assuming tests are run from project root
try:
    from src.scheduler import JobScheduler
    from src.route_fetcher import RouteFetcher
    from src.storage.base import DataStorage
    from src.data_models import RouteData
except ImportError:
    # Fallback for different execution context (e.g. if PYTHONPATH is not set up)
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from src.scheduler import JobScheduler
    from src.route_fetcher import RouteFetcher
    from src.storage.base import DataStorage
    from src.data_models import RouteData


@pytest.fixture
def mock_route_fetcher(mocker: MockerFixture) -> MagicMock:
    return mocker.MagicMock(spec=RouteFetcher)

@pytest.fixture
def mock_data_storage(mocker: MockerFixture) -> MagicMock:
    return mocker.MagicMock(spec=DataStorage)

@pytest.fixture
def origin_coords() -> tuple[float, float]:
    return (48.0, 11.0)

@pytest.fixture
def dest_coords() -> tuple[float, float]:
    return (48.1, 11.1)

@pytest.fixture
def default_scheduler_params(
    mock_route_fetcher: MagicMock,
    mock_data_storage: MagicMock,
    origin_coords: tuple[float, float],
    dest_coords: tuple[float, float]
) -> dict:
    return {
        "route_fetcher": mock_route_fetcher,
        "data_storage": mock_data_storage,
        "origin_coords": origin_coords,
        "dest_coords": dest_coords,
        "frequency_per_hour": 4,
        "start_time_route_to_dest": 7,
        "end_time_route_to_dest": 10,
        "start_time_route_to_origin": 16,
        "end_time_route_to_origin": 19,
        "weekdays": [0, 1, 2, 3, 4]  # Mon-Fri
    }

@pytest.fixture
def scheduler_instance(default_scheduler_params: dict) -> JobScheduler:
    return JobScheduler(**default_scheduler_params)

@pytest.fixture
def berlin_tz() -> pytz.BaseTzInfo: # Added type hint
    return pytz.timezone("Europe/Berlin") # type: ignore


class TestJobSchedulerInit:
    def test_valid_initialization(self, default_scheduler_params: dict):
        scheduler = JobScheduler(**default_scheduler_params)
        assert scheduler.frequency_per_hour == 4
        assert scheduler.interval_seconds == 900  # 3600 / 4
        assert scheduler.hour_range_to_dest == (7, 10)
        assert scheduler.hour_range_to_origin == (16, 19)

    def test_invalid_frequency(self, default_scheduler_params: dict):
        params = default_scheduler_params.copy()
        params["frequency_per_hour"] = 0
        with pytest.raises(ValueError, match="Frequency per hour must be a positive integer."):
            JobScheduler(**params)
        
        params["frequency_per_hour"] = -1
        with pytest.raises(ValueError, match="Frequency per hour must be a positive integer."):
            JobScheduler(**params)

    def test_invalid_time_ranges(self, default_scheduler_params: dict):
        params = default_scheduler_params.copy()
        params["start_time_route_to_dest"] = 10
        params["end_time_route_to_dest"] = 7  # start >= end
        with pytest.raises(ValueError, match="start_time_route_to_dest must be less than end_time_route_to_dest."):
            JobScheduler(**params)

        params = default_scheduler_params.copy()
        params["start_time_route_to_origin"] = 19
        params["end_time_route_to_origin"] = 16  # start >= end
        with pytest.raises(ValueError, match="start_time_route_to_origin must be less than end_time_route_to_origin."):
            JobScheduler(**params)

        params = default_scheduler_params.copy()
        params["start_time_route_to_dest"] = 25  # out of bounds
        with pytest.raises(ValueError, match="Invalid start_time_route_to_dest. Must be between 0 and 24."):
            JobScheduler(**params)


class TestJobSchedulerGetNextFetchTime:
    @pytest.fixture
    def scheduler(self, mock_route_fetcher, mock_data_storage, origin_coords, dest_coords) -> JobScheduler:
        # Scheduler with freq=4 (15 min interval), Mon-Fri, Dest: 7-9, Origin: 16-18
        return JobScheduler(
            route_fetcher=mock_route_fetcher,
            data_storage=mock_data_storage,
            origin_coords=origin_coords,
            dest_coords=dest_coords,
            frequency_per_hour=4,
            start_time_route_to_dest=7,
            end_time_route_to_dest=10,
            start_time_route_to_origin=16,
            end_time_route_to_origin=19,
            weekdays=[0, 1, 2, 3, 4]  # Mon-Fri
        )

    def test_now_before_first_slot_today(self, scheduler: JobScheduler, berlin_tz):
        now = berlin_tz.localize(datetime(2024, 3, 4, 6, 0, 0))  # Monday 06:00
        expected_next_fetch = berlin_tz.localize(datetime(2024, 3, 4, 7, 0, 0))
        assert scheduler.get_next_fetch_time(now) == expected_next_fetch

    def test_now_in_dest_slot(self, scheduler: JobScheduler, berlin_tz):
        now = berlin_tz.localize(datetime(2024, 3, 4, 7, 5, 0))  # Monday 07:05
        expected_next_fetch = berlin_tz.localize(datetime(2024, 3, 4, 7, 15, 0))
        assert scheduler.get_next_fetch_time(now) == expected_next_fetch

    def test_now_exactly_on_dest_slot_start(self, scheduler: JobScheduler, berlin_tz):
        now = berlin_tz.localize(datetime(2024, 3, 4, 7, 0, 0))  # Monday 07:00
        # Expects next interval because current logic is `reference_time > now` for selection
        expected_next_fetch = berlin_tz.localize(datetime(2024, 3, 4, 7, 15, 0))
        assert scheduler.get_next_fetch_time(now) == expected_next_fetch

    def test_now_in_origin_slot(self, scheduler: JobScheduler, berlin_tz):
        now = berlin_tz.localize(datetime(2024, 3, 4, 16, 20, 0))  # Monday 16:20
        expected_next_fetch = berlin_tz.localize(datetime(2024, 3, 4, 16, 30, 0))
        assert scheduler.get_next_fetch_time(now) == expected_next_fetch

    def test_now_between_slots_today(self, scheduler: JobScheduler, berlin_tz):
        now = berlin_tz.localize(datetime(2024, 3, 4, 10, 30, 0))  # Monday 10:30 (after dest, before origin)
        expected_next_fetch = berlin_tz.localize(datetime(2024, 3, 4, 16, 0, 0))
        assert scheduler.get_next_fetch_time(now) == expected_next_fetch

    def test_now_after_all_slots_today_friday(self, scheduler: JobScheduler, berlin_tz):
        now = berlin_tz.localize(datetime(2024, 3, 8, 20, 0, 0))  # Friday 20:00
        expected_next_fetch = berlin_tz.localize(datetime(2024, 3, 11, 7, 0, 0))  # Next Monday 07:00
        assert scheduler.get_next_fetch_time(now) == expected_next_fetch

    def test_now_on_non_scheduled_weekday(self, scheduler: JobScheduler, berlin_tz):
        now = berlin_tz.localize(datetime(2024, 3, 9, 8, 0, 0))  # Saturday 08:00
        expected_next_fetch = berlin_tz.localize(datetime(2024, 3, 11, 7, 0, 0))  # Next Monday 07:00
        assert scheduler.get_next_fetch_time(now) == expected_next_fetch

    def test_frequency_one_per_hour(self, mock_route_fetcher, mock_data_storage, origin_coords, dest_coords, berlin_tz):
        scheduler = JobScheduler(
            route_fetcher=mock_route_fetcher, data_storage=mock_data_storage,
            origin_coords=origin_coords, dest_coords=dest_coords,
            frequency_per_hour=1,  # Every hour
            start_time_route_to_dest=7, end_time_route_to_dest=10,
            start_time_route_to_origin=16, end_time_route_to_origin=19,
            weekdays=[0]  # Monday
        )
        now = berlin_tz.localize(datetime(2024, 3, 4, 7, 5, 0))  # Monday 07:05
        expected_next_fetch = berlin_tz.localize(datetime(2024, 3, 4, 8, 0, 0))
        assert scheduler.get_next_fetch_time(now) == expected_next_fetch

    def test_near_end_of_dest_range(self, scheduler: JobScheduler, berlin_tz):
        # Monday 09:50:00. `hour_range_to_dest` is (7,10) -> 7,8,9.
        # Next slot in this range would be 10:00 if it were inclusive, but it's not.
        # So, it should jump to the origin range at 16:00.
        now = berlin_tz.localize(datetime(2024, 3, 4, 9, 50, 0))  # Monday
        expected_next_fetch = berlin_tz.localize(datetime(2024, 3, 4, 16, 0, 0))
        assert scheduler.get_next_fetch_time(now) == expected_next_fetch


class TestJobSchedulerRun:
    @pytest.fixture
    def run_scheduler(self, mock_route_fetcher, mock_data_storage, origin_coords, dest_coords) -> JobScheduler:
        # Dest: 8-8:59, Origin: 17-17:59, Mon, Freq=4
        return JobScheduler(
            route_fetcher=mock_route_fetcher,
            data_storage=mock_data_storage,
            origin_coords=origin_coords,
            dest_coords=dest_coords,
            frequency_per_hour=4,
            start_time_route_to_dest=8,
            end_time_route_to_dest=9,
            start_time_route_to_origin=17,
            end_time_route_to_origin=18,
            weekdays=[0]  # Monday
        )

    @pytest.fixture
    def sample_route_data(self, origin_coords, dest_coords, berlin_tz) -> RouteData:
        return RouteData(
            origin_lat=origin_coords[0], origin_lon=origin_coords[1],
            dest_lat=dest_coords[0], dest_lon=dest_coords[1],
            distance_m=1000, duration_s=100, duration_in_traffic_s=120,
            start_time=berlin_tz.localize(datetime(2024, 3, 4, 8, 0, 0)) # Placeholder, will be updated
        )

    def test_run_fetches_to_dest_and_saves(
        self, run_scheduler: JobScheduler, mock_route_fetcher: MagicMock, mock_data_storage: MagicMock,
        origin_coords, dest_coords, sample_route_data: RouteData,
        mocker: MockerFixture, berlin_tz
    ):
        mocker.patch('builtins.print') # Suppress print
        mock_sleep = mocker.patch('time.sleep')

        initial_now = berlin_tz.localize(datetime(2024, 3, 4, 7, 59, 50))  # Monday, 10s before 8:00
        fetch_time = berlin_tz.localize(datetime(2024, 3, 4, 8, 0, 0))

        with freeze_time(initial_now) as frozen_datetime:
            # Mock get_next_fetch_time and capture the mock object
            mock_get_next_fetch_time = mocker.patch.object(run_scheduler, 'get_next_fetch_time', side_effect=[fetch_time, StopIteration])
            
            # Route fetcher returns data, its start_time will be based on frozen_datetime at fetch
            sample_route_data.start_time = fetch_time # Adjust expected data
            mock_route_fetcher.get_current_route_data.return_value = sample_route_data
            
            def advance_time_and_assert_sleep(seconds):
                assert seconds == pytest.approx(10.0) # 08:00:00 - 07:59:50
                frozen_datetime.move_to(fetch_time)
            mock_sleep.side_effect = advance_time_and_assert_sleep

            with pytest.raises(StopIteration): # To break the infinite loop for testing
                run_scheduler.run()

            mock_get_next_fetch_time.assert_any_call(initial_now) # Use the captured mock for assertion
            mock_sleep.assert_called_once()
            
            mock_route_fetcher.get_current_route_data.assert_called_once_with(
                origin_cords=origin_coords,
                dest_cords=dest_coords
            )
            mock_data_storage.save.assert_called_once_with(sample_route_data)

    def test_run_fetches_to_origin_and_saves(
        self, run_scheduler: JobScheduler, mock_route_fetcher: MagicMock, mock_data_storage: MagicMock,
        origin_coords, dest_coords, sample_route_data: RouteData,
        mocker: MockerFixture, berlin_tz
    ):
        mocker.patch('builtins.print')
        mock_sleep = mocker.patch('time.sleep')

        initial_now = berlin_tz.localize(datetime(2024, 3, 4, 16, 59, 50))  # Monday, 10s before 17:00
        fetch_time = berlin_tz.localize(datetime(2024, 3, 4, 17, 0, 0))

        with freeze_time(initial_now) as frozen_datetime:
            # Mock get_next_fetch_time (no assertion on its calls in this specific test, but good practice if needed)
            _ = mocker.patch.object(run_scheduler, 'get_next_fetch_time', side_effect=[fetch_time, StopIteration])
            sample_route_data.start_time = fetch_time # Adjust expected data
            mock_route_fetcher.get_current_route_data.return_value = sample_route_data

            def advance_time_and_assert_sleep(seconds):
                assert seconds == pytest.approx(10.0)
                frozen_datetime.move_to(fetch_time)
            mock_sleep.side_effect = advance_time_and_assert_sleep

            with pytest.raises(StopIteration):
                run_scheduler.run()

            mock_route_fetcher.get_current_route_data.assert_called_once_with(
                origin_cords=dest_coords,  # Swapped for "to_origin"
                dest_cords=origin_coords
            )
            mock_data_storage.save.assert_called_once_with(sample_route_data)

    def test_run_no_data_fetched(
        self, run_scheduler: JobScheduler, mock_route_fetcher: MagicMock, mock_data_storage: MagicMock,
        mocker: MockerFixture, berlin_tz: pytz.BaseTzInfo
    ):
        mock_print = mocker.patch('builtins.print') # Mock print to check its calls
        mock_sleep = mocker.patch('time.sleep')

        initial_now = berlin_tz.localize(datetime(2024, 3, 4, 7, 59, 50)) # Monday
        fetch_time = berlin_tz.localize(datetime(2024, 3, 4, 8, 0, 0))

        with freeze_time(initial_now) as frozen_datetime:
            # Mock get_next_fetch_time (no assertion on its calls in this specific test)
            _ = mocker.patch.object(run_scheduler, 'get_next_fetch_time', side_effect=[fetch_time, StopIteration])
            mock_route_fetcher.get_current_route_data.return_value = None # Simulate API error
            
            mock_sleep.side_effect = lambda seconds: frozen_datetime.move_to(fetch_time)

            with pytest.raises(StopIteration):
                run_scheduler.run()
            
            mock_route_fetcher.get_current_route_data.assert_called_once()
            mock_data_storage.save.assert_not_called()
            
            # Check for the specific print message
            printed_messages = "".join(c[0][0] for c in mock_print.call_args_list if c[0])
            assert "No data fetched or an error occurred during fetch" in printed_messages