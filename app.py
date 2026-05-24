import pandas as pd
from flask import Flask, render_template, request, send_file, jsonify
import tempfile
import os
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

app = Flask(__name__)

# Configuración de carpetas temporales para que el navegador vea las imágenes
UPLOAD_FOLDER = 'static/frames'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ==========================================
# CONFIGURACIÓN DE GOOGLE DRIVE API
# ==========================================
# ¡Pega aquí el ID de tu carpeta principal!
MAIN_FOLDER_ID = '1uAT53DkI8J6BaiREw-9-shcM-97chyVI'

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# LÓGICA SEGURA DE CREDENCIALES
google_creds_env = os.environ.get('GOOGLE_CREDENTIALS_JSON')

if google_creds_env:
    # Si estamos en la nube (Render), lee la variable de entorno secreta
    creds_dict = json.loads(google_creds_env)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    # Si estamos en tu computadora local, lee el archivo
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)

drive_service = build('drive', 'v3', credentials=creds)


def get_drive_folders(parent_id):
    """Busca todas las subcarpetas dentro de una carpeta principal."""
    query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name)", orderBy="name").execute()
    return results.get('files', [])

def get_drive_images(folder_id):
    """Busca todas las imágenes dentro de una subcarpeta y las ordena."""
    query = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name)", orderBy="name").execute()
    return results.get('files', [])

# ==========================================
# RUTAS DEL SERVIDOR WEB
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get_folders', methods=['GET'])
def get_folders():
    """Le entrega a la página web la lista de videos (subcarpetas)."""
    folders = get_drive_folders(MAIN_FOLDER_ID)
    return jsonify({'folders': folders})

@app.route('/api/load_video', methods=['POST'])
def load_video():
    """Descarga los frames de un video específico desde Drive y los prepara para la web."""
    data = request.json
    folder_id = data.get('folder_id')
    folder_name = data.get('folder_name')

    if not folder_id:
        return jsonify({'error': 'No se especificó la carpeta'}), 400

    # Crear una carpeta local temporal para este video
    video_dir = os.path.join(UPLOAD_FOLDER, folder_name)
    os.makedirs(video_dir, exist_ok=True)

    images = get_drive_images(folder_id)
    frame_urls = []

    # Descargar cada imagen de Google Drive a nuestra carpeta temporal
    for img in images:
        file_path = os.path.join(video_dir, img['name'])
        
        # Solo descargamos si no la habíamos descargado antes (para que sea más rápido)
        if not os.path.exists(file_path):
            request_api = drive_service.files().get_media(fileId=img['id'])
            fh = io.FileIO(file_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request_api)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
        
        # Guardar la ruta web para el navegador
        frame_urls.append(f"/{file_path}")

    return jsonify({
        'video_name': folder_name,
        'frames': frame_urls
    })

@app.route('/save_csv', methods=['POST'])
def save_csv():
    """Guarda el archivo CSV con las coordenadas."""
    data = request.json
    points = data.get('points', [])
    video_name = data.get('video_name', 'video_desconocido')
    
    if not points:
        return jsonify({"error": "No hay puntos para guardar"}), 400

    temp_dir = tempfile.mkdtemp()
    csv_path = os.path.join(temp_dir, f"{video_name}_etiquetas.csv")
    
    df = pd.DataFrame(points)
    df.to_csv(csv_path, index=False, encoding='utf-8')

    return send_file(csv_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
