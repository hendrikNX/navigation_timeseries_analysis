import unittest
import os
import tempfile
import sqlite3
from datetime import datetime, timezone, timedelta

# Assuming your project root is in PYTHONPATH or you run tests from the root directory
# If not, you might need to adjust sys.path or how you run tests.
from src.storage.sqlite_storage import SQLiteStorage
from src.data_models import RouteData # Make sure RouteData is accessible

class TestSQLiteStorage(unittest.TestCase):

    def setUp(self):
        """
        Set up a temporary database for each test.
        """
        # Create a temporary directory that will be cleaned up automatically
        self.test_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir = self.test_dir_obj.name
        self.db_path = os.path.join(self.test_dir, "test_routes.db")
        self.storage = SQLiteStorage(db_path=self.db_path)

        # Sample data for testing
        self.sample_route_times = RouteData(
            origin_lat=52.5200,
            origin_lon=13.4050,
            dest_lat=48.8566,
            dest_lon=2.3522,
            distance_m=1050000,
            duration_s=36000,
            duration_in_traffic_s=37800,
            start_time=datetime(2023, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
        )

    def tearDown(self):
        """
        Clean up the temporary directory and database file after each test.
        """
        self.test_dir_obj.cleanup()

    def test_01_initialization_creates_db_and_table(self):
        """
        Test that the database file and the 'route_times' table are created upon initialization.
        """
        self.assertTrue(os.path.exists(self.db_path), "Database file should be created.")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='route_times';")
        table_exists = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(table_exists, "Table 'route_times' should exist.")
        self.assertEqual(table_exists[0], 'route_times')

    def test_02_initialization_creates_directory_if_not_exists(self):
        """
        Test that the directory for the database is created if it doesn't exist.
        """
        with tempfile.TemporaryDirectory() as temp_root_dir:
            nested_db_dir = os.path.join(temp_root_dir, "data_subdir")
            db_path_in_subdir = os.path.join(nested_db_dir, "test_routes_subdir.db")

            # Ensure the subdir does not exist initially
            self.assertFalse(os.path.exists(nested_db_dir))

            # Initialize storage, which should create the subdir
            SQLiteStorage(db_path=db_path_in_subdir)

            self.assertTrue(os.path.exists(nested_db_dir), "Database directory should be created.")
            self.assertTrue(os.path.exists(db_path_in_subdir), "Database file in subdirectory should be created.")

    def test_03_save_data_correctly(self):
        """
        Test that data is saved correctly to the database.
        """
        self.storage.save(self.sample_route_times)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row # Access columns by name
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM route_times WHERE origin_lat = ?;", (self.sample_route_times.origin_lat,))
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row, "Data should be found in the database.")
        self.assertEqual(row['origin_lat'], self.sample_route_times.origin_lat)
        self.assertEqual(row['origin_lon'], self.sample_route_times.origin_lon)
        self.assertEqual(row['dest_lat'], self.sample_route_times.dest_lat)
        self.assertEqual(row['dest_lon'], self.sample_route_times.dest_lon)
        self.assertEqual(row['distance_m'], self.sample_route_times.distance_m)
        self.assertEqual(row['duration_s'], self.sample_route_times.duration_s)
        self.assertEqual(row['duration_in_traffic_s'], self.sample_route_times.duration_in_traffic_s)
        self.assertEqual(row['start_time'], self.sample_route_times.start_time.isoformat(),
                         "Start time should be stored as an ISO format string.")

    def test_04_save_multiple_data_points(self):
        """
        Test saving multiple data points.
        """
        self.storage.save(self.sample_route_times)
        another_route_data = RouteData(**{**self.sample_route_times.__dict__, "origin_lat": 50.0})
        self.storage.save(another_route_data)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM route_times;")
        count = cursor.fetchone()[0]
        conn.close()

        self.assertEqual(count, 2, "Should be two records in the database.")

    def test_05_load_data_empty_db(self):
        """
        Test loading data from an empty database.
        """
        loaded_data = self.storage.load(limit=10)
        self.assertEqual(len(loaded_data), 0, "Should return an empty list from an empty database.")

    def test_06_load_data_with_limit(self):
        """
        Test loading data with a specific limit.
        """
        # Save 3 data points with different start times
        time_now = datetime(2023, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
        data1 = RouteData(**{**self.sample_route_times.__dict__, "start_time": time_now, "distance_m": 100})
        data2 = RouteData(**{**self.sample_route_times.__dict__, "start_time": time_now - timedelta(hours=1), "distance_m": 200})
        data3 = RouteData(**{**self.sample_route_times.__dict__, "start_time": time_now - timedelta(hours=2), "distance_m": 300})

        self.storage.save(data1)
        self.storage.save(data2)
        self.storage.save(data3)

        # Load with limit 2
        loaded_data = self.storage.load(limit=2)
        self.assertEqual(len(loaded_data), 2, "Should load exactly 2 records.")

        # Check if the most recent ones are loaded (data1 and data2)
        loaded_distances = [d.distance_m for d in loaded_data]
        self.assertIn(100, loaded_distances, "Data1 should be loaded.")
        self.assertIn(200, loaded_distances, "Data2 should be loaded.")
        self.assertNotIn(300, loaded_distances, "Data3 should not be loaded due to limit.")

    def test_07_load_data_order_and_structure(self):
        """
        Test that data is loaded in descending order of start_time and has the correct structure.
        """
        time_now = datetime(2023, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
        # Create data points with specific start times for ordering
        route_data_recent = RouteData(**{**self.sample_route_times.__dict__, "start_time": time_now, "distance_m": 1})
        route_data_older = RouteData(**{**self.sample_route_times.__dict__, "start_time": time_now - timedelta(minutes=10), "distance_m": 2})
        route_data_oldest = RouteData(**{**self.sample_route_times.__dict__, "start_time": time_now - timedelta(minutes=20), "distance_m": 3})

        self.storage.save(route_data_older) # Save out of order
        self.storage.save(route_data_oldest)
        self.storage.save(route_data_recent)

        loaded_data = self.storage.load(limit=3)
        self.assertEqual(len(loaded_data), 3, "Should load all 3 records.")

        # Verify order (most recent first)
        self.assertEqual(loaded_data[0].distance_m, route_data_recent.distance_m)
        self.assertEqual(loaded_data[1].distance_m, route_data_older.distance_m)
        self.assertEqual(loaded_data[2].distance_m, route_data_oldest.distance_m)

        # Verify structure of the first loaded item
        first_item = loaded_data[0]
        self.assertIsInstance(first_item, RouteData, "Loaded item should be an intance of RouteData.")
        self.assertEqual(first_item.origin_lat, route_data_recent.origin_lat)
        self.assertEqual(first_item.origin_lon, route_data_recent.origin_lon)
        self.assertEqual(first_item.dest_lat, route_data_recent.dest_lat)
        self.assertEqual(first_item.dest_lon, route_data_recent.dest_lon)
        self.assertEqual(first_item.distance_m, route_data_recent.distance_m)
        self.assertEqual(first_item.duration_s, route_data_recent.duration_s)
        self.assertEqual(first_item.duration_in_traffic_s, route_data_recent.duration_in_traffic_s)
        self.assertEqual(first_item.start_time, route_data_recent.start_time)

    def _get_all_records(self, order_by="id ASC"):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM route_times ORDER BY {order_by}")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def _get_record_count(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM route_times")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def test_08_delete_by_single_id(self):
        """Test deleting a record by a single ID."""
        data1 = RouteData(**{**self.sample_route_times.__dict__, "distance_m": 101})
        data2 = RouteData(**{**self.sample_route_times.__dict__, "distance_m": 102})
        self.storage.save(data1) # Assumes ID 1
        self.storage.save(data2) # Assumes ID 2

        self.storage.delete(id=1)
        self.assertEqual(self._get_record_count(), 1, "Should be one record left.")
        remaining_records = self._get_all_records()
        self.assertEqual(remaining_records[0]['distance_m'], 102, "Data2 should remain.")

    def test_09_delete_by_list_of_ids(self):
        """Test deleting records by a list of IDs."""
        data1 = RouteData(**{**self.sample_route_times.__dict__, "distance_m": 201, "start_time": datetime(2023,1,1,10,0,0,tzinfo=timezone.utc)})
        data2 = RouteData(**{**self.sample_route_times.__dict__, "distance_m": 202, "start_time": datetime(2023,1,1,11,0,0,tzinfo=timezone.utc)})
        data3 = RouteData(**{**self.sample_route_times.__dict__, "distance_m": 203, "start_time": datetime(2023,1,1,12,0,0,tzinfo=timezone.utc)})
        self.storage.save(data1) # ID 1
        self.storage.save(data2) # ID 2
        self.storage.save(data3) # ID 3

        self.storage.delete(id=[1, 3])
        self.assertEqual(self._get_record_count(), 1, "Should be one record left after deleting by list.")
        remaining_records = self._get_all_records()
        self.assertEqual(remaining_records[0]['distance_m'], 202, "Data2 should remain.")

        # Test with empty list
        self.storage.delete(id=[])
        self.assertEqual(self._get_record_count(), 1, "Deleting with empty ID list should not change record count.")

        # Test with non-existent IDs in list
        self.storage.delete(id=[99, 100])
        self.assertEqual(self._get_record_count(), 1, "Deleting with non-existent IDs should not change record count.")

    def test_10_delete_by_single_time(self):
        """Test deleting records by a single timestamp (matching the minute)."""
        time_base = datetime(2023, 10, 27, 10, 0, 0, tzinfo=timezone.utc)
        data_t1_s0 = RouteData(**{**self.sample_route_times.__dict__, "start_time": time_base, "distance_m": 301})
        data_t1_s30 = RouteData(**{**self.sample_route_times.__dict__, "start_time": time_base + timedelta(seconds=30), "distance_m": 302})
        data_t2 = RouteData(**{**self.sample_route_times.__dict__, "start_time": time_base + timedelta(minutes=5), "distance_m": 303})

        self.storage.save(data_t1_s0)
        self.storage.save(data_t1_s30)
        self.storage.save(data_t2)

        self.storage.delete(time=time_base) # Should delete records from 10:00:00 to 10:00:59
        self.assertEqual(self._get_record_count(), 1, "Should be one record left.")
        remaining_records = self._get_all_records()
        self.assertEqual(remaining_records[0]['distance_m'], 303, "Only data_t2 should remain.")

    def test_11_delete_by_list_of_times(self):
        """Test deleting records by a list of timestamps."""
        time1 = datetime(2023, 10, 27, 11, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(2023, 10, 27, 12, 0, 0, tzinfo=timezone.utc)
        time3 = datetime(2023, 10, 27, 13, 0, 0, tzinfo=timezone.utc)

        data_at_time1 = RouteData(**{**self.sample_route_times.__dict__, "start_time": time1, "distance_m": 401})
        data_at_time2 = RouteData(**{**self.sample_route_times.__dict__, "start_time": time2 + timedelta(seconds=15), "distance_m": 402})
        data_at_time3 = RouteData(**{**self.sample_route_times.__dict__, "start_time": time3, "distance_m": 403})

        self.storage.save(data_at_time1)
        self.storage.save(data_at_time2)
        self.storage.save(data_at_time3)

        self.storage.delete(time=[time1, time3]) # Delete records matching 11:00 and 13:00
        self.assertEqual(self._get_record_count(), 1, "Should be one record left.")
        remaining_records = self._get_all_records()
        self.assertEqual(remaining_records[0]['distance_m'], 402, "Only data_at_time2 should remain.")

    def test_12_delete_by_time_range(self):
        """Test deleting records within a time range."""
        t_before = datetime(2023, 10, 27, 13, 59, 0, tzinfo=timezone.utc)
        t_start_range = datetime(2023, 10, 27, 14, 0, 0, tzinfo=timezone.utc)
        t_in_range1 = datetime(2023, 10, 27, 14, 30, 0, tzinfo=timezone.utc)
        t_in_range2 = datetime(2023, 10, 27, 14, 59, 59, tzinfo=timezone.utc) # Almost at end of range minute
        t_end_range = datetime(2023, 10, 27, 15, 0, 0, tzinfo=timezone.utc) # Exclusive end for range
        t_after = datetime(2023, 10, 27, 15, 1, 0, tzinfo=timezone.utc)

        data_before = RouteData(**{**self.sample_route_times.__dict__, "start_time": t_before, "distance_m": 501})
        data_in1 = RouteData(**{**self.sample_route_times.__dict__, "start_time": t_in_range1, "distance_m": 502})
        data_in2 = RouteData(**{**self.sample_route_times.__dict__, "start_time": t_in_range2, "distance_m": 503})
        data_at_start_range = RouteData(**{**self.sample_route_times.__dict__, "start_time": t_start_range, "distance_m": 504})
        data_after = RouteData(**{**self.sample_route_times.__dict__, "start_time": t_after, "distance_m": 505})

        self.storage.save(data_before)
        self.storage.save(data_in1)
        self.storage.save(data_in2)
        self.storage.save(data_at_start_range)
        self.storage.save(data_after)

        # Delete records from 14:00:00 (inclusive) to 15:00:00 (exclusive)
        self.storage.delete(time_range=(t_start_range, t_end_range))
        self.assertEqual(self._get_record_count(), 2, "Two records should remain (before and after range).")

        remaining_distances = {r['distance_m'] for r in self._get_all_records()}
        self.assertIn(501, remaining_distances, "Data before range should remain.")
        self.assertIn(505, remaining_distances, "Data after range should remain.")
        self.assertNotIn(502, remaining_distances, "Data in range 1 should be deleted.")
        self.assertNotIn(503, remaining_distances, "Data in range 2 should be deleted.")
        self.assertNotIn(504, remaining_distances, "Data at start of range should be deleted.")

    def test_13_delete_invalid_parameters(self):
        """Test delete method with invalid parameters."""
        with self.assertRaisesRegex(ValueError, "Deletion requires exactly one condition."):
            self.storage.delete()

        with self.assertRaisesRegex(ValueError, "Deletion requires exactly one condition."):
            self.storage.delete(id=1, time=datetime.now(timezone.utc))

        with self.assertRaisesRegex(ValueError, "time_range must be a tuple of two datetime objects."):
            self.storage.delete(time_range=(datetime.now(timezone.utc), "not-a-datetime")) # type: ignore

        with self.assertRaisesRegex(ValueError, "Start of time_range must be before end of time_range."):
            now = datetime.now(timezone.utc)
            self.storage.delete(time_range=(now, now - timedelta(hours=1)))

    def test_14_delete_non_existent_data(self):
        """Test deleting data that does not exist, ensuring no errors and no changes."""
        data1 = RouteData(**{**self.sample_route_times.__dict__, "distance_m": 601})
        self.storage.save(data1)
        initial_count = self._get_record_count()

        # Delete by non-existent ID
        self.storage.delete(id=999)
        self.assertEqual(self._get_record_count(), initial_count, "Count should not change for non-existent ID.")

        # Delete by non-existent list of IDs
        self.storage.delete(id=[888, 777])
        self.assertEqual(self._get_record_count(), initial_count, "Count should not change for non-existent ID list.")

        # Delete by time not in DB
        non_existent_time = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.storage.delete(time=non_existent_time)
        self.assertEqual(self._get_record_count(), initial_count, "Count should not change for non-existent time.")

        # Delete by list of times not in DB
        self.storage.delete(time=[non_existent_time, non_existent_time + timedelta(hours=1)])
        self.assertEqual(self._get_record_count(), initial_count, "Count should not change for non-existent time list.")

        # Delete by time range not in DB
        non_existent_range_start = datetime(2001, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        non_existent_range_end = datetime(2001, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
        self.storage.delete(time_range=(non_existent_range_start, non_existent_range_end))
        self.assertEqual(self._get_record_count(), initial_count, "Count should not change for non-existent time range.")

if __name__ == '__main__':
    unittest.main()