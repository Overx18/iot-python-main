# app.py
from flask import Flask, request, jsonify
import base64
from pymongo import MongoClient
from google.cloud import vision
from google.oauth2 import service_account
import os
from datetime import datetime # Asegúrate de importar datetime

app = Flask(__name__)

# --- Configuración ---
# Reemplaza con tu cadena de conexión de MongoDB Atlas
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://<user>:<password>@<cluster-url>/<dbname>?retryWrites=true&w=majority")
# Reemplaza con el ID de tu proyecto de Google Cloud
credentials = service_account.Credentials.from_service_account_file(
    'proyecto-iot-462403-3c411bc2b93d.json'
)

# --- Inicializar Clientes ---
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["falta"] # O especifica tu base de datos: db = mongo_client["nombre_de_tu_base_de_datos"]
    print("¡Conectado a MongoDB Atlas con éxito!")
except Exception as e:
    print(f"Error al conectar a MongoDB Atlas: {e}")
    # Maneja el error apropiadamente, quizás sal o lanza una excepción
    # exit()

vision_client = vision.ImageAnnotatorClient(credentials=credentials)

@app.route('/data_ingestion', methods=['POST'])
def data_ingestion():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"status": "error", "message": "No se recibieron datos JSON"}), 400

        # Extraer datos de la petición
        sensor_data = data.get('sensors')
        gps_data = data.get('gps')
        base64_image = data.get('image') # Asumiendo que la imagen se envía con la clave 'image'

        recognized_plate = None

        if base64_image:
            try:
                # Decodificar la imagen Base64
                image_bytes = base64.b64decode(base64_image)

                # Preparar imagen para Vision AI
                image = vision.Image(content=image_bytes)

                # Realizar detección de texto (OCR)
                response = vision_client.text_detection(image=image)
                texts = response.text_annotations

                if texts:
                    # La primera anotación de texto suele ser el texto completo detectado
                    full_text = texts[0].description
                    # Aquí podrías necesitar un análisis más sofisticado para extraer específicamente la matrícula
                    # Para simplificar, asumiremos que el primer texto reconocido es la matrícula o la contiene
                    recognized_plate = full_text.split('\n')[0] # Tomando la primera línea como posible matrícula

                if response.error.message:
                    print(f"Error de Vision AI: {response.error.message}")
                    # Opcionalmente registra este error
            except Exception as e:
                print(f"Error al procesar la imagen con Vision AI: {e}")
                # Continuar con la ingesta de datos incluso si el procesamiento de la imagen falla
        else:
            print("No se recibió imagen Base64.")

        # Preparar datos para MongoDB
        record = {
            "timestamp": datetime.now(),
            "sensors": sensor_data,
            "gps": gps_data,
            "recognized_plate": recognized_plate,
            # Podrías querer almacenar la imagen Base64 en la DB si es necesario, pero considera los límites de tamaño
            # "base64_image": base64_image # Descomenta si quieres almacenarla
        }

        # Insertar en MongoDB
        collection_name = os.environ.get("MONGO_COLLECTION", "falta")
        db[collection_name].insert_one(record)

        return jsonify({"status": "success", "message": "Datos ingeridos con éxito", "recognized_plate": recognized_plate}), 200

    except Exception as e:
        print(f"Ocurrió un error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def hello_world():
    return "Hello, World!", 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))