import re
import os
from flask import Flask, request, jsonify
from google.cloud import vision
from google.oauth2 import service_account
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

app = Flask(__name__)
load_dotenv()

# --- Configuración Google Cloud y API Vision AI ---
#cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
#credentials = service_account.Credentials.from_service_account_file(cred_path)
vision_client = vision.ImageAnnotatorClient()#credentials=credentials)

# --- Conexcion MongoDB ---
MONGO_URI = os.environ.get("MONGO_URI")
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

@app.route('/api/plates', methods=['POST'])
def procesar_plates():
    try:
        if request.content_type != "image/jpeg":
            return jsonify({"status": "error", "message": "Solo se acepta Content-Type: image/jpeg"}), 415

        # Leer imagen JPEG cruda desde el body
        image_bytes = request.data
        # Procesar imagen con Vision AI
        image = vision.Image(content=image_bytes)
        response = vision_client.text_detection(image=image)
        texts = response.text_annotations
        recognized_plate = None
        # Extraer placa
        if texts:
            recognized_plate = extract_plate(texts[0].description)

        if response.error.message:
            print(f"Error de Vision AI: {response.error.message}")

        # Guardar en MongoDB
        if recognized_plate:
            plate_data = {
                "plate": recognized_plate,
                "timestamp": datetime.now(),
                "source": "camera"
            }
            plates_collection.insert_one(plate_data)

        return jsonify({
            "status": "success",
            "recognized_plate": recognized_plate,
            "timestamp": datetime.now().isoformat()
        }), 200

    except Exception as e:
        print(f"Error al procesar imagen: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def hello():
    return "API de OCR para placas activada y recibir datos de los sensores", 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
