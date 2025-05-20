import csv
import os
from dataclasses import astuple
from datetime import datetime, timezone, timedelta
import tempfile

from .base import DataStorage, DeleteParams, Unpack
try:
    from ..data_models import RouteData # For application context
except ImportError:
    from data_models import RouteData # For standalone testing if needed

class CsvStorage(DataStorage):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._initialize_csv()

    def _initialize_csv(self):
        # Ensure the directory for the CSV file exists
        csv_dir = os.path.dirname(self.file_path)
        if csv_dir and not os.path.exists(csv_dir):
            os.makedirs(csv_dir, exist_ok=True)
            print(f"Created directory for CSV file: {csv_dir}")

        if not os.path.exists(self.file_path) or os.path.getsize(self.file_path) == 0:
            # Create dummy RouteData instance to get headers in correct order
            # Ensure a timezone-aware datetime for dummy RouteData
            dummy_dt = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            header = RouteData(0,0,0,0,0,0,0,dummy_dt).get_field_names()
            with open(self.file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(header)

    def save(self, route_data: RouteData) -> None:
        # Convert datetime to ISO format string for consistent CSV storage
        data_tuple = list(astuple(route_data))
        # Assuming start_time is the last field as per RouteData definition
        # and its __post_init__ ensures it's a datetime object.
        data_tuple[-1] = route_data.start_time.isoformat()
        with open(self.file_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(data_tuple)
        print(f"Data saved to CSV: {self.file_path}")

    def load(self, limit: int) -> list[dict]:
        records = []
        if not os.path.exists(self.file_path):
            return []

        with open(self.file_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric types from string
                try:
                    row['origin_lat'] = float(row['origin_lat'])
                    row['origin_lon'] = float(row['origin_lon'])
                    row['dest_lat'] = float(row['dest_lat'])
                    row['dest_lon'] = float(row['dest_lon'])
                    row['distance_m'] = int(row['distance_m'])
                    row['duration_s'] = int(row['duration_s'])
                    row['duration_in_traffic_s'] = int(row['duration_in_traffic_s'])
                    # 'start_time' is kept as an ISO string, which is fine for JSON output.
                    # If conversion to datetime is needed here, it would be:
                    # row['start_time'] = datetime.fromisoformat(row['start_time'])
                except (ValueError, KeyError) as e:
                    print(f"Skipping row due to parsing error: {row}, error: {e}")
                    continue
                records.append(row)

        # Sort by start_time descending (most recent first)
        # Ensure start_time exists and handle potential None or empty string if data is malformed
        records.sort(key=lambda x: x.get('start_time', ''), reverse=True)
        return records[:limit]

    def delete(self, **kwargs: Unpack[DeleteParams]):
        if not kwargs or len(kwargs) > 1:
            raise ValueError("Deletion requires exactly one condition.")

        # Determine the single criterion provided
        criterion_key = list(kwargs.keys())[0]
        criterion_value = kwargs[criterion_key]

        if not os.path.exists(self.file_path):
            print(f"CSV file {self.file_path} does not exist. Nothing to delete.")
            return

        all_rows = []
        try:
            with open(self.file_path, 'r', newline='') as f_read:
                reader = csv.reader(f_read)
                all_rows = list(reader)
        except FileNotFoundError: # Should be caught by os.path.exists, but defensive
            print(f"CSV file {self.file_path} not found during delete. Nothing to delete.")
            return

        if not all_rows:
            print(f"CSV file {self.file_path} is empty. Nothing to delete.")
            return

        header = all_rows[0]
        data_rows = all_rows[1:]

        if not data_rows:
            print(f"CSV file {self.file_path} has no data rows. Nothing to delete.")
            return

        start_time_idx = -1
        if criterion_key == 'time' or criterion_key == 'time_range':
            try:
                start_time_idx = header.index('start_time')
            except ValueError:
                raise ValueError(f"'start_time' column not found in CSV header of {self.file_path}. Cannot perform time-based deletion.")

        rows_to_keep = []
        deleted_count = 0

        # Logging the processing action (similar to SQLiteStorage)
        # This is done after initial checks and before the main loop for clarity
        if criterion_key == 'time':
            time_crit_val = criterion_value
            if isinstance(time_crit_val, list):
                times_list_str = [self._time_round_minutes(t).strftime('%Y-%m-%d %H:%M') for t in time_crit_val if isinstance(t, datetime)]
                print(f"Processing CSV deletion based on timestamp(s): {times_list_str}")
            elif isinstance(time_crit_val, datetime):
                time_str = self._time_round_minutes(time_crit_val).strftime('%Y-%m-%d %H:%M')
                print(f"Processing CSV deletion based on timestamp: {time_str}")
            else:
                raise ValueError("Invalid type for 'time' criterion. Expected datetime or list of datetimes.")

        elif criterion_key == 'time_range':
            time_range_val = criterion_value
            if not (isinstance(time_range_val, tuple) and len(time_range_val) == 2 and
                    isinstance(time_range_val[0], datetime) and isinstance(time_range_val[1], datetime)):
                raise ValueError("time_range must be a tuple of two datetime objects.")
            if time_range_val[0] >= time_range_val[1]:
                raise ValueError("Start of time_range must be before end of time_range.")
            start_str = self._time_round_minutes(time_range_val[0]).isoformat()
            end_str = self._time_round_minutes(time_range_val[1]).isoformat()
            print(f"Processing CSV deletion based on timestamp range: {start_str} to {end_str}")

        elif criterion_key == 'id':
            id_val = criterion_value
            if isinstance(id_val, list):
                print(f"Processing CSV deletion based on id list: {id_val}")
                if not id_val:
                    print("CSV Deletion: No IDs provided in the list, no rows will be deleted by ID.")
            else: # isinstance(id_val, int)
                print(f"Processing CSV deletion based on id: {id_val}")

        for idx, row_list_str in enumerate(data_rows):
            keep_row = True
            row_start_time_dt = None

            if criterion_key == 'time' or criterion_key == 'time_range':
                try:
                    row_start_time_dt = datetime.fromisoformat(row_list_str[start_time_idx])
                except (IndexError, ValueError) as e:
                    print(f"Warning: Skipping row {idx+1} due to invalid start_time: {e}. Row: {row_list_str}")
                    rows_to_keep.append(row_list_str) # Keep malformed rows by default
                    continue

            if criterion_key == 'time':
                target_times_dt = [criterion_value] if not isinstance(criterion_value, list) else criterion_value
                match_found = False
                for t_dt in target_times_dt:
                    rounded_target_minute = self._time_round_minutes(t_dt)
                    if row_start_time_dt and rounded_target_minute <= row_start_time_dt < (rounded_target_minute + timedelta(minutes=1)):
                        match_found = True
                        break
                if match_found: keep_row = False
            elif criterion_key == 'time_range':
                start_range_dt, end_range_dt = criterion_value # Already validated
                rounded_start = self._time_round_minutes(start_range_dt)
                rounded_end = self._time_round_minutes(end_range_dt)
                if row_start_time_dt and rounded_start <= row_start_time_dt < rounded_end:
                    keep_row = False
            elif criterion_key == 'id':
                current_row_number = idx + 1 # 1-indexed
                target_ids = [criterion_value] if not isinstance(criterion_value, list) else criterion_value
                if not target_ids: pass # No IDs to delete
                elif current_row_number in target_ids: keep_row = False

            if keep_row:
                rows_to_keep.append(row_list_str)
            else:
                deleted_count += 1

        if deleted_count > 0:
            temp_file_path = None
            try:
                # Write to a temporary file in the same directory for atomic os.replace
                base_dir = os.path.dirname(self.file_path)
                with tempfile.NamedTemporaryFile(mode='w', newline='', delete=False, dir=base_dir, suffix='.tmpcsv') as tmpfile:
                    temp_file_path = tmpfile.name
                    writer = csv.writer(tmpfile)
                    writer.writerow(header)
                    writer.writerows(rows_to_keep)
                os.replace(temp_file_path, self.file_path)
                print(f"Deleted {deleted_count} rows from CSV: {self.file_path} based on criteria: {kwargs}")
            except Exception as e:
                print(f"Error during CSV file update: {e}. Original file may be intact.")
                if temp_file_path and os.path.exists(temp_file_path):
                    try: os.remove(temp_file_path)
                    except OSError as rm_e: print(f"Could not remove temporary file {temp_file_path}: {rm_e}")
                raise
        else:
            print(f"No rows matched CSV deletion criteria in {self.file_path}. File unchanged. Criteria: {kwargs}")