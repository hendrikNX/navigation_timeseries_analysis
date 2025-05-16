# 🚗💨 Navigation Timeseries Analysis

This project periodically fetches route information (such as travel duration and distance) between a defined origin and destination. The data is collected at scheduled intervals and stored, allowing for timeseries analysis of navigation conditions.

## 🛠️ Core Functionality

*   🗺️ **Route Data Fetching**: Utilizes an external API (e.g., Google Maps Distance Matrix API) to get current route details, including duration in traffic.
*   ⏰ **Scheduling**: A configurable scheduler runs jobs to fetch data at specified frequencies, times of day, and on particular weekdays.
*   💾 **Data Storage**: Saves the collected route data to a persistent store (e.g., CSV files, potentially databases).
*   ⚙️ **Configuration**: Settings for API keys, coordinates, schedule, and storage are managed via environment variables and a configuration file.

## 🎯 Purpose

The primary goal is to build a dataset of travel times and conditions over various periods. This data can then be used for analysis, such as understanding traffic patterns, predicting travel times, or personal commute optimization.