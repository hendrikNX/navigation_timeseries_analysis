import streamlit as st
import requests
from datetime import datetime, timedelta
import sys
import os
import pandas as pd
import numpy as np
import plotly.express as px

# Ensure the project root is in sys.path to allow absolute import from src.
# This assumes dashboard.py is in src/dashboard/
# os.path.dirname(os.path.abspath(__file__)) gives the directory of dashboard.py (src/dashboard)
# Then, os.path.join(..., '..', '..') goes up two levels to the project root.
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.data_models import RouteData, route_data_list_to_dataframe
from src.config import API_BASE_URL, FETCH_FREQUENCY_PER_HOUR

class Dashboard:
    def __init__(self):
        self.api_url = f"http://192.168.178.104:5000/api/routes"
        # self.api_url = f"{API_BASE_URL}/api/routes"
        self.raw_data_df = None
        self.processed_data_df = pd.DataFrame()
        
        # Calculate gap threshold based on scheduler frequency
        if FETCH_FREQUENCY_PER_HOUR > 0:
            scheduler_interval_seconds = 3600 / FETCH_FREQUENCY_PER_HOUR
            # Define a gap as anything more than, e.g., 2 times the expected interval
            self.gap_threshold = timedelta(seconds=scheduler_interval_seconds * 2)
        else:
            # Default to a reasonable gap if frequency is not positive (e.g., 1 hour)
            self.gap_threshold = timedelta(hours=1)

    def _load_data(self):
        try:
            response = requests.get(self.api_url, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors
            
            route_list_json = response.json()
            if not route_list_json: # Handle empty response from API
                self.raw_data_df = pd.DataFrame(columns=RouteData.get_static_field_names())
                self.processed_data_df = self.raw_data_df.copy()
                return
            
            route_list = [RouteData(
                route['origin_lat'], route['origin_lon'],
                route['dest_lat'], route['dest_lon'],
                route['distance_m'], route['duration_s'],
                route['duration_in_traffic_s'], datetime.fromisoformat(route['start_time'])
            ) for route in route_list_json]
            
            self.raw_data_df = route_data_list_to_dataframe(route_list)
            self._process_data_for_plotting()

        except requests.exceptions.RequestException as e:
            st.error(f"Error loading data from API: {e}")
            self.raw_data_df = pd.DataFrame(columns=RouteData.get_static_field_names())
            self.processed_data_df = self.raw_data_df.copy()
        except Exception as e: # Catch other potential errors (e.g., JSON decoding)
            st.error(f"An unexpected error occurred while loading data: {e}")
            self.raw_data_df = pd.DataFrame(columns=RouteData.get_static_field_names())
            self.processed_data_df = self.raw_data_df.copy()

    def _process_data_for_plotting(self):
        if self.raw_data_df is None or self.raw_data_df.empty:
            self.processed_data_df = pd.DataFrame(columns=RouteData.get_static_field_names())
            return
    
        df = self.raw_data_df.copy()
        
        if len(df) < 2: # Not enough data to have gaps
            self.processed_data_df = df
            return

        new_rows_list = []
        new_rows_list.append(df.iloc[0].to_dict()) # Add the first row
        
        for i in range(len(df) - 1):
            current_row = df.iloc[i]
            next_row = df.iloc[i+1]
            time_diff = next_row['start_time'] - current_row['start_time']
            
            if time_diff > self.gap_threshold:
                # Insert a NaN point in the middle of the gap to break the line
                nan_time = current_row['start_time'] + time_diff / 2
                nan_row_dict = {col: np.nan for col in df.columns}
                nan_row_dict['start_time'] = nan_time
                # Ensure the y-axis column for the plot is NaN
                if 'duration_in_traffic_s' in nan_row_dict:
                    nan_row_dict['duration_in_traffic_s'] = np.nan
                new_rows_list.append(nan_row_dict)
            
            new_rows_list.append(next_row.to_dict()) # Add the next actual data point
        
        self.processed_data_df = pd.DataFrame(new_rows_list)
        self.processed_data_df['start_time'] = pd.to_datetime(self.processed_data_df['start_time'])
        self.processed_data_df = self.processed_data_df.sort_values(by='start_time').reset_index(drop=True)
    
    def display(self):
        st.title("Route Travel Time Dashboard")

        if self.raw_data_df is None: # Data loading might have failed before _process_data_for_plotting
            st.warning("Data could not be loaded. Check API connection and logs.")
            return
        if self.raw_data_df.empty:
            st.info("No data available from the API.")
            return

        st.subheader("Raw Data Preview")
        st.dataframe(self.raw_data_df.head())

        st.subheader("Travel Time (with traffic)")
        if not self.processed_data_df.empty and 'duration_in_traffic_s' in self.processed_data_df.columns:
            plot_df = self.processed_data_df.copy()
            plot_df['duration_in_traffic_min'] = plot_df['duration_in_traffic_s'] / 60
            # Ensure NaNs are propagated to the new column
            plot_df.loc[plot_df['duration_in_traffic_s'].isna(), 'duration_in_traffic_min'] = np.nan
            
            plot_df['start_time'] = plot_df['start_time'].astype(str)
            fig = px.line(plot_df, x='start_time', y='duration_in_traffic_min',
                          title="Travel Time Over Time (Gaps Excluded)",
                          labels={'start_time': "Time", 'duration_in_traffic_min': "Duration in Traffic (minutes)"})
            # fig.update_xaxes(type='date')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data or 'duration_in_traffic_s' column missing for plotting.")

if __name__ == "__main__":
    dashboard = Dashboard()
    dashboard._load_data()
    dashboard.display()