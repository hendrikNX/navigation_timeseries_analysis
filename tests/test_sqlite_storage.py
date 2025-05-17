import unittest
import os
import tempfile
import sqlite3
from datetime import datetime, timezone

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

if __name__ == '__main__':
    unittest.main()