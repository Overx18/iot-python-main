import easyocr
import cv2
import numpy as np

reader = None

def detectar_placa(image_bytes):
    global reader
    if reader is None:
        reader = easyocr.Reader(['en'])  # Se carga una sola vez al primer request

    np_img = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    img = cv2.resize(img, (640, 480))  # Reduce uso de RAM y tiempo

    results = reader.readtext(img)

    posibles_placas = []
    for (bbox, texto, conf) in results:
        if len(texto) >= 6 and any(char.isdigit() for char in texto):
            posibles_placas.append((texto, conf))

    posibles_placas.sort(key=lambda x: x[1], reverse=True)
    return posibles_placas[0][0] if posibles_placas else "NO DETECTADA"
