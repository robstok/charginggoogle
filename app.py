import streamlit as st
import pandas as pd
import plotly.express as px
import re
import ast
from google.oauth2.service_account import Credentials
import gspread

# Google Sheets Setup
st.title("Site Listing Management")

try:
    # Authenticate with Google Sheets API using credentials and scopes
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(credentials)

    # Open the spreadsheet
    spreadsheet = client.open("eleport_google_maps")
    
    # List all worksheet names for verification
    worksheets = spreadsheet.worksheets()
    worksheet_names = [ws.title for ws in worksheets]
    
    # Access the desired worksheet by name
    sheet = spreadsheet.worksheet("Sheet1")
    
    # Get all records from the worksheet
    data = sheet.get_all_records()
    
    # Convert data to a DataFrame
    df = pd.DataFrame(data)

except Exception as e:
    st.error(f"An error occurred: {e}")

# Convert "TRUE"/"FALSE" strings to Python booleans
df['connector_match'] = df['connector_match'].apply(lambda x: True if x == "TRUE" else False if x == "FALSE" else x)
df['power_match'] = df['power_match'].apply(lambda x: True if x == "TRUE" else False if x == "FALSE" else x)

# Normalize missing values in `external_reference`
df['external_reference'] = df['external_reference'].replace(["", "NULL", "N/A"], pd.NA)
df['missing_external_reference'] = df['external_reference'].isna()

df['placeId'] = df['placeId'].replace(["", "NULL", "N/A"], pd.NA)
df['missing_placeId'] = df['placeId'].isna()

# Parse missing connectors columns
df['missing_in_google'] = df['missing_in_google'].fillna("{}").apply(eval)
df['missing_in_db'] = df['missing_in_db'].fillna("{}").apply(eval)
df['connector_match'] = df['connector_match'].fillna(False).astype(bool)
df['power_match'] = df['power_match'].fillna(False).astype(bool)

# Add the status column
df['status'] = df['connector_match'].apply(lambda x: 'Fully Correct' if x else 'Discrepant')

# Handle missing identifiers
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

# Dashboard Title
st.title("Site Listing Management")

# Section 1: Stacked Bar Chart Summary
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
    title="Locations Missing in Google Maps vs Potential Duplicate on Google Maps",
    color="Category",
    color_discrete_map={
        "Missing Locations in Google Maps": "#3498db",  # Blue
        "Potential Duplicate": "#9b59b6"  # Purple
    }
)
st.plotly_chart(stacked_bar)

# Section 2: Missing on Google Maps
st.subheader("Stations Missing on Google Maps")
missing_google = df[df['missing_placeId']]
st.dataframe(missing_google[['name', 'street_db', 'city_db', 'external_reference']])

# Section 3: Missing in Database
st.subheader("Potential Duplicates")
missing_db = df[df['missing_external_reference']]
st.dataframe(missing_db[['name', 'street_google', 'city_google', 'placeId','googleMapsUri']])

# Section 4: Map of Stations
st.subheader("Station Map")

# Add hover information
df['hover_info'] = df['name'] + " - " + df['street_db'] + ", " + df['city_db']

# Colors and sizes for map points based on status and missing data
def assign_map_category(row):
    if row['missing_placeId']:
        return "Missing Location in Google Maps"
    elif row['missing_external_reference']:
        return "Missing Location in Database"
    elif row['status'] == "Fully Correct":
        return "Fully Correct"
    else:
        return "Discrepant"

df['map_category'] = df.apply(assign_map_category, axis=1)

# Define color mapping for categories
category_color_map = {
    "Missing Location in Google Maps": "#3498db",  # Blue
    "Missing Location in Database": "#9b59b6",     # Purple
    "Fully Correct": "#2ecc71",                    # Green
    "Discrepant": "#e74c3c"                        # Red
}

# Create the map with categorical colors
station_map = px.scatter_mapbox(
    df,
    lat='latitude',
    lon='longitude',
    color='map_category',  # Use the category column for the legend
    color_discrete_map=category_color_map,  # Assign colors to categories
    title="Station Locations",
    mapbox_style="carto-positron",
    zoom=4,  # Zoom out to level 4 for a broader view
    hover_name='hover_info'  # Show name, street, and city on hover
)

# Display the map
st.plotly_chart(station_map)

## Section 5: Detailed Discrepancy Table
st.subheader("Detailed Discrepancy Table")

# Filter for stations with no missing locations
matched_stations = df[
    ~df['missing_placeId'] & ~df['missing_external_reference']
]

# Order the table by connector_match and then power_match
matched_stations_sorted = matched_stations.sort_values(
    by=['connector_match', 'power_match'], ascending=[True, True]
)

# Highlight rows with missing data
def highlight_missing(row):
    if row['connector_match'] != True or row['power_match'] != True:
        return ['background-color: lightcoral'] * len(row)
    return [''] * len(row)

# Apply the styling to the dataframe
styled_table = matched_stations_sorted[
    ['external_reference', 'name', 'street_db', 'city_db', 'missing_in_google', 'missing_in_db', 'connector_match', 'power_match']
].style.apply(highlight_missing, axis=1)

# Display the styled dataframe
st.dataframe(styled_table)
