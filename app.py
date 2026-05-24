import os
import json
import io
import pandas as pd
from flask import Flask, render_template, request, send_file, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

app = Flask(__name__)

UPLOAD_FOLDER = 'static/frames'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MAIN_FOLDER_ID = '1uAT53DkI8J6BaiREw-9-shcM-97chyVI'

SCOPES = ['https://www.googleapis.com/auth/drive']

google_creds_env = os.environ.get('GOOGLE_CREDENTIALS_JSON')

if google_creds_env:
    creds_dict = json.loads(google_creds_env)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)

drive_service = build('drive', 'v3', credentials=creds)

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
    data = request.json
    points = data.get('points', [])
    video_name = data.get('video_name', 'video_desconocido')
    folder_id = data.get('folder_id')
    
    if not points or not folder_id:
        return jsonify({"error": "Faltan datos"}), 400

    df = pd.DataFrame(points)
    csv_string = df.to_csv(index=False)
    
    file_metadata = {
        'name': f"{video_name}_etiquetas.csv",
        'parents': [folder_id]
    }
    
    query = f"name = '{file_metadata['name']}' and '{folder_id}' in parents and trashed=false"
    existing_files = drive_service.files().list(q=query, fields="files(id)").execute().get('files', [])

    media = MediaIoBaseUpload(io.BytesIO(csv_string.encode('utf-8')), mimetype='text/csv')
    
    if existing_files:
        file_id = existing_files[0]['id']
        drive_service.files().update(fileId=file_id, media_body=media).execute()
        message = "CSV actualizado"
    else:
        drive_service.files().create(body=file_metadata, media_body=media).execute()
        message = "CSV creado"

    return jsonify({"success": True, "message": message})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
