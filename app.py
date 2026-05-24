import pandas as pd
from flask import Flask, render_template, request, send_file
import tempfile
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save_csv', methods=['POST'])
def save_csv():
    """Recibe los puntos de la interfaz y devuelve un archivo CSV."""
    data = request.json
    points = data.get('points', [])
    video_name = data.get('video_name', 'video_desconocido')
    
    if not points:
        return {"error": "No hay puntos para guardar"}, 400

    # Crear el CSV en una carpeta temporal segura
    temp_dir = tempfile.mkdtemp()
    csv_path = os.path.join(temp_dir, f"{video_name}_etiquetas.csv")
    
    # Pandas convierte nuestra lista de puntos a CSV automáticamente
    df = pd.DataFrame(points)
    df.to_csv(csv_path, index=False, encoding='utf-8')

    # Enviar el archivo al navegador para su descarga
    return send_file(csv_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
