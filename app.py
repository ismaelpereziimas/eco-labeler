import os
import json
import io
import pandas as pd
from flask import Flask, render_template, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

app = Flask(__name__)

UPLOAD_FOLDER = 'static/frames'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MAIN_FOLDER_ID = '1uAT53DkI8J6BaiREw-9-shcM-97chyVI'
SHEET_ID = '1XbCOIxB3-VupP8V-r5Ocdq68Wl4vHd8gfPhZhgIoWcE'

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

google_creds_env = os.environ.get('GOOGLE_CREDENTIALS_JSON')

if google_creds_env:
    creds_dict = json.loads(google_creds_env)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)

drive_service = build('drive', 'v3', credentials=creds)
sheets_service = build('sheets', 'v4', credentials=creds)

def get_drive_folders(parent_id):
    query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name)", orderBy="name").execute()
    return results.get('files', [])

def get_drive_images(folder_id):
    query = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name)", orderBy="name").execute()
    return results.get('files', [])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get_folders', methods=['GET'])
def get_folders():
    try:
        folders = get_drive_folders(MAIN_FOLDER_ID)
        return jsonify({'folders': folders})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/load_video', methods=['POST'])
def load_video():
    data = request.json
    folder_id = data.get('folder_id')
    folder_name = data.get('folder_name')

    if not folder_id:
        return jsonify({'error': 'No se especificó la carpeta'}), 400

    video_dir = os.path.join(UPLOAD_FOLDER, folder_name)
    os.makedirs(video_dir, exist_ok=True)

    images = get_drive_images(folder_id)
    frame_urls = []

    for img in images:
        file_path = os.path.join(video_dir, img['name'])
        
        if not os.path.exists(file_path):
            request_api = drive_service.files().get_media(fileId=img['id'])
            fh = io.FileIO(file_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request_api)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
        
        frame_urls.append(f"/{file_path}")

    return jsonify({
        'video_name': folder_name,
        'frames': frame_urls
    })

@app.route('/save_csv', methods=['POST'])

def save_csv():
    try:
        data = request.json
        points = data.get('points', [])
        video_name = data.get('video_name', 'video_desconocido')
        
        if not points:
            return jsonify({"error": "No hay puntos"}), 400

        sheets_service = build('sheets', 'v4', credentials=creds)
        
        values = []
        for p in points:
            values.append([video_name, p['Frame'], p['X'], p['Y'], p['Valve']])
        
        body = {'values': values}
        
        response = sheets_service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range='Hoja1!A2',
            valueInputOption='RAW',
            body=body
        ).execute()
        
        return jsonify({"success": True, "message": "Datos guardados"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
