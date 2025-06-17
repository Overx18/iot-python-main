import re
import os
from flask import Flask, request, jsonify
from google.cloud import vision
from google.oauth2 import service_account
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
import uuid
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
load_dotenv()

# --- Configuración Google Cloud y API Vision AI ---
# cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
# credentials = service_account.Credentials.from_service_account_file(cred_path)
vision_client = vision.ImageAnnotatorClient()#)

# --- Conexcion MongoDB ---
MONGO_URI = os.environ.get("MONGO_URI")

# --- UPLOAD FOLDER ---
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["iot-db"] # Especifica la base de datos
    print("¡Conectado a MongoDB Atlas con éxito!")
except Exception as e:
    print(f"Error al conectar a MongoDB Atlas: {e}")
    # Maneja el error apropiadamente, quizás sal o lanza una excepción

# --- Colecciones ---
plates_collection = db["plates_data"]  # Para placas de vehículos
sensors_collection = db["sensors_data"]  # Para datos de sensores

#Funcion para extraer el formato de la placa de todo el texto encontrado en la imagen
def extract_plate(text):

    """
    Extrae placas con formato: 3 caracteres (letras/números) + guión + 3 caracteres (letras/números).
    Ejemplos válidos: VUS-123, ABC-1A2, 1B3-45C
    """
    plate_pattern = re.compile(
        r'\b[A-Z0-9]{3}-[A-Z0-9]{3}\b',  # Formato: XXX-XXX (letras/números)
        re.IGNORECASE
    )

    matches = plate_pattern.findall(text.upper().replace(" ", ""))
    return matches[0] if matches else None

# --- Endpoint 1: Procesamiento de imágenes (placas) ---

@app.route('/api/plates', methods=['POST'])
def procesar_plates():
    try:
        if request.content_type != "image/jpeg":
            return jsonify({"status": "error", "message": "Solo se acepta Content-Type: image/jpeg"}), 415

        # Leer imagen JPEG cruda desde el body
        image_bytes = request.data

        # Convertir los bytes en una imagen con Pillow
        image = Image.open(io.BytesIO(image_bytes))

        # Crear el efecto espejo (flip horizontal)
        mirrored_image = image.transpose(Image.FLIP_LEFT_RIGHT)

        # Convertir la imagen de vuelta a bytes
        img_byte_arr = io.BytesIO()
        mirrored_image.save(img_byte_arr, format='JPEG')
        mirrored_image_bytes = img_byte_arr.getvalue()

        # Generate unique filename
        filename = f"{uuid.uuid4().hex}.jpg"
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        # Save image to disk
        with open(file_path, 'wb') as f:
            f.write(mirrored_image_bytes)

        # Procesar imagen con Vision AI
        image = vision.Image(content=mirrored_image_bytes)
        response = vision_client.text_detection(image=image)
        texts = response.text_annotations

        recognized_plate = None
        # Extraer placa
        if texts:
            recognized_plate = extract_plate(texts[0].description)

        if response.error.message:
            print(f"Error de Vision AI: {response.error.message}")

        # Guardar en MongoDB
        #if recognized_plate:
        plate_data = {
            "plate": recognized_plate,
            "timestamp": datetime.now(),
            "source": "ESP32-CAM",
            "image_path": file_path
        }
        plates_collection.insert_one(plate_data)

        return jsonify({
            "status": "success",
            "recognized_plate": recognized_plate,
            "timestamp": datetime.now().isoformat(),
            "image_path": file_path
        }), 200

    except Exception as e:
        print(f"Error al procesar imagen: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Endpoint 2: Datos de sensores (gas, GPS, etc.) ---
@app.route('/api/sensors', methods=['POST'])
def process_sensors():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "Datos JSON requeridos"}), 400

        # Guardar en MongoDB
        sensor_data = {
            "CO": data.get("gas1", 0),  # MQ7
            "CO2": data.get("gas2", 0),  # MQ2
            "Calidad del aire": data.get("gas3", 0),  # MQ135
            "distancia": round(data.get("distancia", 0.0), 2),
            "id": data.get("id", 0),
            "timestamp": datetime.now()
        }
        sensors_collection.insert_one(sensor_data)

        return jsonify({
            "status": "success",
            "message": "Datos de sensores guardados",
            "timestamp": datetime.now().isoformat()
        }), 200

    except Exception as e:

        return jsonify({"status": "error", "message": str(e)}), 500

# Get endpoints para obtener datos de placas y sensores
@app.route('/api/plates', methods=['GET'])
def get_plates():
    plates = list(plates_collection.find({}, {'_id': 0}))
    return jsonify({"status": "success", "plates": plates}), 200

@app.route('/api/sensors', methods=['GET'])
def get_sensors():
    sensors = list(sensors_collection.find({}, {'_id': 0}))
    return jsonify({"status": "success", "sensors": sensors}), 200

# --- Endpoint de prueba ---
@app.route('/', methods=['GET'])
def hello():
    return "API de OCR para placas activada y recibir datos de los sensores", 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
