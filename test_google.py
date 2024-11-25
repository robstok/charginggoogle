from google.oauth2.service_account import Credentials
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import io

# Define the scopes
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Load credentials from a service account file
credentials = Credentials.from_service_account_file(
    '/Users/robinstokkel/Downloads/huizensites-409516-36c635b6ec06.json', 
    scopes=scopes
)

# Authorize gspread
gc = gspread.authorize(credentials)

# Access the Google Sheet by key
sheet_key = "1HX_Py4cHTtZSLEAeR7w0hDFAgmUvS5_MznUrWNoJosI"  # Replace with your sheet key
gs = gc.open_by_key(sheet_key)

# Access a specific worksheet
worksheet = gs.worksheet('Sheet1')  # Replace with your worksheet name
data = worksheet.get_all_records()

# Print data from Google Sheets
print("Data from Google Sheet:")
print(data)

# Initialize the Google Drive API client
drive_service = build('drive', 'v3', credentials=credentials)

# Example: Access a file from Google Drive
file_id = "1HX_Py4cHTtZSLEAeR7w0hDFAgmUvS5_MznUrWNoJosI"  # Replace with your file ID

try:
    # Get the file metadata to determine the file name and MIME type
    file_metadata = drive_service.files().get(fileId=file_id, fields='name, mimeType').execute()
    file_name = file_metadata.get('name')
    mime_type = file_metadata.get('mimeType')

    print(f"File Name: {file_name}")
    print(f"MIME Type: {mime_type}")

    # Initialize a BytesIO object to receive the file content
    fh = io.BytesIO()

    if mime_type.startswith('application/vnd.google-apps'):
        # It's a Google Docs Editor file; determine the export format
        if mime_type == 'application/vnd.google-apps.spreadsheet':
            # Export as CSV
            request = drive_service.files().export_media(fileId=file_id,
                                                         mimeType='text/csv')
            export_filename = f"{file_name}.csv"
        elif mime_type == 'application/vnd.google-apps.document':
            # Export as PDF
            request = drive_service.files().export_media(fileId=file_id,
                                                         mimeType='application/pdf')
            export_filename = f"{file_name}.pdf"
        elif mime_type == 'application/vnd.google-apps.presentation':
            # Export as PPTX
            request = drive_service.files().export_media(fileId=file_id,
                                                         mimeType='application/vnd.openxmlformats-officedocument.presentationml.presentation')
            export_filename = f"{file_name}.pptx"
        else:
            print(f"Unsupported Google Docs Editor MIME type: {mime_type}")
            exit(1)

        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Export Download {int(status.progress() * 100)}%.")
    else:
        # It's a binary file; use get_media
        request = drive_service.files().get_media(fileId=file_id)
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%.")

        export_filename = file_name

    # Save the downloaded content to a local file
    with open(export_filename, "wb") as f:
        f.write(fh.getvalue())

    print(f"File downloaded successfully as '{export_filename}'.")

except googleapiclient.errors.HttpError as error:
    print(f"An error occurred: {error}")
