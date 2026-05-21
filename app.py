from flask import Flask, render_template, request, jsonify, send_file
import cv2
import pandas as pd
import os
import zipfile
from datetime import datetime
import shutil
import tempfile

app = Flask(__name__)

# Configuración de carpetas temporales para los videos
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    """Renderiza la interfaz principal (HTML)."""
    return render_template('index.html')

@app.route('/upload_video', methods=['POST'])
def upload_video():
    """Recibe el video, extrae los frames como imágenes y devuelve sus rutas."""
    if 'video' not in request.files:
        return jsonify({'error': 'No se envió ningún video'}), 400
        
    file = request.files['video']
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_folder = os.path.join(UPLOAD_FOLDER, session_id)
    os.makedirs(session_folder, exist_ok=True)
    
    video_path = os.path.join(session_folder, file.filename)
    file.save(video_path)
    
    # Extraer frames con OpenCV
    cap = cv2.VideoCapture(video_path)
    frame_urls = []
    frame_idx = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_filename = f"frame_{frame_idx}.jpg"
        frame_path = os.path.join(session_folder, frame_filename)
        cv2.imwrite(frame_path, frame)
        
        # Guardamos la URL relativa para que el navegador pueda cargar la imagen
        frame_urls.append(f"/{frame_path}")
        frame_idx += 1
        
    cap.release()
    
    return jsonify({
        'session_id': session_id,
        'frames': frame_urls,
        'video_name': os.path.splitext(file.filename)[0]
    })

@app.route('/download_dataset', methods=['POST'])
def download_dataset():
    """Recibe los puntos desde JS, dibuja en los frames originales y empaqueta en ZIP."""
    data = request.json
    points = data.get('points', [])
    session_id = data.get('session_id')
    
    if not points or not session_id:
        return jsonify({'error': 'Faltan datos o puntos'}), 400

    session_folder = os.path.join(UPLOAD_FOLDER, session_id)
    temp_dir = tempfile.mkdtemp()
    
    # Crear carpetas de salida
    originales_folder = os.path.join(temp_dir, "originales")
    mitral_folder = os.path.join(temp_dir, "mitral")
    tricuspide_folder = os.path.join(temp_dir, "tricuspide")
    for f in [originales_folder, mitral_folder, tricuspide_folder]:
        os.makedirs(f, exist_ok=True)

    # 1. Guardar Excel
    df = pd.DataFrame(points)
    df.to_excel(os.path.join(temp_dir, "puntos.xlsx"), index=False)

    # 2. Procesar imágenes basándonos en los puntos
    frames_unicos = set([p["Frame"] for p in points])

    for f_idx in frames_unicos:
        # Leer el frame original que extrajimos al inicio
        frame_path = os.path.join(session_folder, f"frame_{f_idx}.jpg")
        base_img = cv2.imread(frame_path)
        
        if base_img is None:
            continue

        cv2.imwrite(os.path.join(originales_folder, f"frame_{f_idx}.png"), base_img)

        mitral_img = base_img.copy()
        tricuspide_img = base_img.copy()

        for row in points:
            if row["Frame"] == f_idx:
                x, y = int(row["X"]), int(row["Y"])
                if row["Valve"] == "Mitral":
                    cv2.circle(mitral_img, (x, y), 6, (0, 0, 255), -1) # Rojo (BGR en OpenCV)
                elif row["Valve"] == "Tricúspide":
                    cv2.circle(tricuspide_img, (x, y), 6, (255, 0, 0), -1) # Azul

        cv2.imwrite(os.path.join(mitral_folder, f"frame_{f_idx}.png"), mitral_img)
        cv2.imwrite(os.path.join(tricuspide_folder, f"frame_{f_idx}.png"), tricuspide_img)

    # 3. Crear ZIP
    zip_path = os.path.join(tempfile.gettempdir(), f"dataset_{session_id}.zip")
    shutil.make_archive(zip_path.replace('.zip', ''), 'zip', temp_dir)

    # Limpieza del directorio temporal
    shutil.rmtree(temp_dir)

    return send_file(zip_path, as_attachment=True)

if __name__ == '__main__':
    # Debug=True reinicia el servidor automáticamente si haces cambios en el código
    app.run(debug=True, port=5000)