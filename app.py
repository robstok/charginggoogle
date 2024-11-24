import streamlit as st
import pandas as pd
import plotly.express as px
import re
from google.oauth2.service_account import Credentials
import gspread

# Google Sheets Setup
st.title("Site Listing Management")
try:
    # Authenticate using Streamlit Secrets
    credentials = st.secrets["gcp_service_account"]
    client = gspread.service_account_from_dict(credentials)

    # Load Google Sheet
    sheet = client.open("Eleport google maps").Sheet1  # Replace with your Google Sheet name
    data = sheet.get_all_records()

    # Convert data to a DataFrame
    df = pd.DataFrame(data)
    st.success("Google Sheet loaded successfully!")
except Exception as e:
    st.error(f"Error loading Google Sheet: {e}")
    st.stop()

# Preprocess the data
df['missing_in_google'] = df['missing_in_google'].fillna("{}").apply(eval)
df['missing_in_db'] = df['missing_in_db'].fillna("{}").apply(eval)
df['connector_match'] = df['connector_match'].fillna(False).astype(bool)
df['power_match'] = df['power_match'].fillna(False).astype(bool)
df['missing_placeId'] = df['placeId'].isna()
df['missing_external_reference'] = df['external_reference'].isna()

# Extract latitude and longitude from geometry
def extract_latitude(geometry):
    if isinstance(geometry, str) and "POINT" in geometry:
        try:
            return float(re.search(r"POINT \(([^ ]+) ([^)]+)\)", geometry).group(2))
        except (AttributeError, ValueError):
            return None
    return None

def extract_longitude(geometry):
    if isinstance(geometry, str) and "POINT" in geometry:
        try:
            return float(re.search(r"POINT \(([^ ]+) ([^)]+)\)", geometry).group(1))
        except (AttributeError, ValueError):
            return None
    return None

df['latitude'] = df['geometry_db'].apply(extract_latitude)
df['longitude'] = df['geometry_db'].apply(extract_longitude)

# Identify rows with invalid geometry
invalid_geometry_rows = df[df['latitude'].isnull() | df['longitude'].isnull()]
st.write("Invalid Geometry Rows", invalid_geometry_rows)

# Combine name, street, and city for filtering and display
df['station_filter'] = df['name'] + " - " + df['street_db'] + ", " + df['city_db']

# Stacked Bar Chart Summary
st.header("Summary of Missing Stations")
missing_counts = pd.DataFrame({
    "Category": ["Missing Locations in Google Maps", "Potential Duplicates"],
    "Count": [
        len(df[df['missing_placeId']]),
        len(df[df['missing_external_reference']])
    ]
})
stacked_bar = px.bar(
    missing_counts,
    x="Category",
    y="Count",
    title="Locations Missing in Google Maps vs Potential Duplicates",
    color="Category",
    color_discrete_map={
        "Missing Locations in Google Maps": "#3498db",  # Blue
        "Potential Duplicate": "#9b59b6"  # Purple
    }
)
st.plotly_chart(stacked_bar)

# Missing on Google Maps
st.subheader("Stations Missing on Google Maps")
missing_google = df[df['missing_placeId']]
st.dataframe(missing_google[['name', 'street_db', 'city_db']])

# Missing in Database
st.subheader("Potential Duplicates")
missing_db = df[df['missing_external_reference']]
st.dataframe(missing_db[['name', 'street_google', 'city_google']])

# Station Map
st.subheader("Station Map")

# Add hover information
df['hover_info'] = df['name'] + " - " + df['street_db'] + ", " + df['city_db']

# Assign map category
def assign_map_category(row):
    if row['missing_placeId']:
        return "Missing Location in Google Maps"
    elif row['missing_external_reference']:
        return "Missing Location in Database"
    elif row['connector_match']:
        return "Fully Correct"
    else:
        return "Discrepant"

df['map_category'] = df.apply(assign_map_category, axis=1)
category_color_map = {
    "Missing Location in Google Maps": "#3498db",
    "Missing Location in Database": "#9b59b6",
    "Fully Correct": "#2ecc71",
    "Discrepant": "#e74c3c"
}
station_map = px.scatter_mapbox(
    df,
    lat='latitude',
    lon='longitude',
    color='map_category',
    color_discrete_map=category_color_map,
    title="Station Locations",
    mapbox_style="carto-positron",
    zoom=4,
    hover_name='hover_info'
)
st.plotly_chart(station_map)

# Detailed Discrepancy Table
st.subheader("Detailed Discrepancy Table")
matched_stations = df[~df['missing_placeId'] & ~df['missing_external_reference']]
matched_stations_sorted = matched_stations.sort_values(by=['connector_match', 'power_match'], ascending=[True, True])
st.dataframe(matched_stations_sorted)

