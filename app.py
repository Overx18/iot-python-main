import re
import os
from flask import Flask, request, jsonify
from google.cloud import vision
from google.oauth2 import service_account
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# --- Carga de Configuración ---
load_dotenv() # Carga las variables de entorno desde el archivo .env

class Config:
    """
    Clase de configuración para cargar variables de entorno.
    """
    MONGO_URI = os.environ.get("MONGO_URI")
    # Si se usa el archivo de credenciales de Google Cloud, se descomenta la siguientes línea:
    # GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    # Convierte la variable FLASK_DEBUG a booleano de forma segura
    DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1", "t")

# --- Inicialización de la Aplicación Flask ---
app = Flask(__name__)
app.config.from_object(Config) # Carga la configuración desde la clase Config

# --- Inicialización del Cliente de Google Cloud Vision AI ---
vision_client = None
try:
    # Si se usa el archivo de credenciales de servicio, se descomenta las siguientes líneas:
    #credentials = service_account.Credentials.from_service_account_file(
    #     app.config["GOOGLE_APPLICATION_CREDENTIALS"]
    # )
    # vision_client = vision.ImageAnnotatorClient(credentials=credentials)
    vision_client = vision.ImageAnnotatorClient() # Inicializa el cliente sin credenciales explícitas si se usa Application Default Credentials
    print("Cliente de Google Cloud Vision AI inicializado.")
except Exception as e:
    print(f"Error al inicializar el cliente de Google Cloud Vision AI: {e}")
    # Considera si la aplicación debe detenerse si no puede inicializar el cliente de Vision AI.

# --- Conexión a MongoDB ---
mongo_client = None
db = None
try:
    mongo_client = MongoClient(app.config["MONGO_URI"])
    db = mongo_client["iot-db"]  # Especifica el nombre de la base de datos
    # El comando ismaster es una forma basica de verificar la conexión.
    mongo_client.admin.command('ismaster')
    print("¡Conectado a MongoDB Atlas con éxito!")
except ConnectionFailure as e:
    print(f"Error al conectar a MongoDB Atlas: {e}")
    # Maneja el error apropiadamente, quizás lanza una excepción.
except Exception as e:
    print(f"Ocurrió un error inesperado durante la conexión a MongoDB: {e}")

# --- Colecciones de MongoDB ---
# Asegúrarse de que db no sea None antes de intentar acceder a las colecciones
plates_collection = None
sensors_collection = None

if db is not None:
    plates_collection = db["plates_data"] if db is not None else None # Para placas de vehículos
    sensors_collection = db["sensors_data"] if db is not None else None # Para datos de sensores
else:
    print("No se pudo establecer la conexión a la base de datos. Las colecciones no estarán disponibles.")

# --- Funciones de ayuda ---
def extract_plate(text: str) -> str | None:
    """
    Extrae placas con formato: 3 caracteres (letras/números) + guión + 3 caracteres (letras/números).
    Ejemplos válidos: VUS-123, ABC-1A2, 1B3-45C
    """
    plate_pattern = re.compile(
        r'\b[A-Z0-9]{3}-[A-Z0-9]{3}\b',  # Formato: XXX-XXX (letras/números)
        re.IGNORECASE # Ignora mayúsculas y minúsculas
    )
    # Normaliza el texto: convierte a mayúsculas y elimina espacios para una mejor coincidencia
    matches = plate_pattern.findall(text.upper().replace(" ", ""))
    return matches[0] if matches else None

# --- Endpoints de la API ---

@app.route('/api/plates', methods=['POST'])
def process_plates():
    """
    Endpoint para procesar imágenes y reconocer placas de vehículos usando Google Cloud Vision AI.
    Acepta imágenes JPEG y almacena las placas reconocidas en MongoDB.
    """
    if not vision_client:
        return jsonify({"status": "error", "message": "Cliente de Vision AI no inicializado."}), 500
    if  plates_collection is None:
        return jsonify({"status": "error", "message": "Base de datos no conectada para placas."}), 500

    if request.content_type != "image/jpeg":
        return jsonify({"status": "error", "message": "Solo se acepta 'Content-Type: image/jpeg'."}), 415

    try:
        image_bytes = request.data
        image = vision.Image(content=image_bytes)
        response = vision_client.text_detection(image=image)
        texts = response.text_annotations

        recognized_plate = None
        if texts:
            # texts[0].description contiene todo el texto detectado en la imagen
            recognized_plate = extract_plate(texts[0].description)

        if response.error.message:
            print(f"Error de Vision AI: {response.error.message}")
            # Devuelve este error al cliente si es crítico
            return jsonify({"status": "error", "message": f"Error de procesamiento de Vision AI: {response.error.message}"}), 500

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
        else:
            return jsonify({
                "status": "success",
                "recognized_plate": None,
                "message": "No se encontró ninguna placa en la imagen.",
                "timestamp": datetime.now().isoformat()
            }), 200

    except Exception as e:
        print(f"Error al procesar la imagen: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/sensors', methods=['POST'])
def process_sensors():
    """
    Endpoint para recibir y almacenar datos de sensores (ej. gas, GPS).
    Espera datos JSON y los almacena en MongoDB.
    """
    if sensors_collection is None:
        return jsonify({"status": "error", "message": "Base de datos no conectada para sensores."}), 500

    try:
        data = request.get_json() # Parsea el cuerpo de la solicitud como JSON
        if not data:
            return jsonify({"status": "error", "message": "Se requieren datos JSON."}), 400

        # Valida campos obligatorios
        required_fields = ["gas1", "gas2", "gas3", "latitude", "longitude"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({"status": "error", "message": f"Faltan campos requeridos: {', '.join(missing_fields)}"}), 400

        sensor_data = {
            **data, # Copia todos los datos recibidos
            "timestamp": datetime.now()
        }
        sensors_collection.insert_one(sensor_data)

        return jsonify({
            "status": "success",
            "message": "Datos de sensores guardados con éxito.",
            "timestamp": datetime.now().isoformat()
        }), 200

    except Exception as e:
        print(f"Error al procesar datos del sensor: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def hello():
    """
    Endpoint raíz para una verificación de estado simple o mensaje de bienvenida.
    """
    return "API para OCR de placas y recepción de datos de sensores activada.", 200

# --- Ejecución principal de la alicación ---
if __name__ == '__main__':
    # Ejecuta la aplicación en modo debug si app.config["DEBUG"] es True
    app.run(debug=app.config["DEBUG"], host='0.0.0.0', port=app.config["PORT"])