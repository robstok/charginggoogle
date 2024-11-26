import streamlit as st
import pandas as pd
import plotly.express as px
import re
import ast
from google.oauth2.service_account import Credentials
import gspread

# Google Sheets Setup
st.title("Listing Management - Google Maps")

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

# Normalize missing values in external_reference
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

# Extract latitude and longitude, with fallback to geometry_google if geometry_db is empty
df['latitude'] = df['geometry_db'].apply(extract_latitude).fillna(
    df['geometry_google'].apply(extract_latitude)
)
df['longitude'] = df['geometry_db'].apply(extract_longitude).fillna(
    df['geometry_google'].apply(extract_longitude)
)

# Combine name, street, and city for filtering and display
df['station_filter'] = df['name'] + " - " + df['street_db'] + ", " + df['city_db']

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

# Section 2: Potential Duplicates
st.subheader("Potential Duplicates on Google Maps")
missing_db = df[df['missing_external_reference']]
st.dataframe(missing_db[['name', 'street_google', 'city_google', 'placeId', 'googleMapsUri']])

# Section 3: Google Maps Status per Station
st.subheader("Google Maps Status per Station")

# Filter records to include only those with a valid external_reference
df = df[df['external_reference'].notna() & (df['external_reference'].str.upper() != 'NULL')]

# Add new columns with default False values for missing entries
new_columns = [
    'Live on Google Maps', 'Status live on Google Maps', 'Coordinates correct',
    'Connectors & Power correct', 'Phone number correct', 'Website correct'
]
for col in new_columns:
    df[col] = df[col].fillna(False)

# Normalize the boolean columns to handle "True"/"False" strings
bool_columns = [
    'Live on Google Maps', 'Status live on Google Maps', 'Coordinates correct',
    'Connectors & Power correct', 'Phone number correct', 'Website correct'
]
for col in bool_columns:
    df[col] = df[col].apply(lambda x: x.strip().lower() == 'true' if isinstance(x, str) else False)

# Highlight rows with any False value in the specified columns
def highlight_false(row):
    if any(row[col] == False for col in bool_columns):  # Highlight if any column is False
        return ['background-color: lightcoral'] * len(row)
    return [''] * len(row)

# Sort the DataFrame to prioritize rows with False values in the specified order
df_sorted = df.sort_values(
    by=bool_columns,  # Sort by the specified columns in the provided order
    ascending=True  # False (treated as lower) comes before True
)

# Display the table with the specified columns
columns_to_display = ['name', 'street_db', 'city_db'] + bool_columns + ['Eco-Movement Status']
styled_table = df_sorted[columns_to_display].style.apply(highlight_false, axis=1)
st.dataframe(styled_table, use_container_width=True)

