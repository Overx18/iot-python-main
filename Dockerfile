# Usa una imagen oficial de Python como base. Hemos elegido una ligera (slim-buster).
FROM python:3.9-slim-buster

# Establece el directorio de trabajo dentro del contenedor. Aquí es donde se copiará tu código.
WORKDIR /app

# Copia el archivo requirements.txt primero para aprovechar el cache de Docker.
# Esto significa que si tus dependencias no cambian, Docker no reinstalará todo cada vez.
COPY requirements.txt .

# Instala las dependencias de Python especificadas en requirements.txt.
# --no-cache-dir evita almacenar el caché de pip, reduciendo el tamaño de la imagen.
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo el contenido del directorio actual (donde está app.py y otros archivos)
# al directorio de trabajo /app dentro del contenedor.
COPY . .

# Define el puerto en el que tu aplicación Flask escuchará. Cloud Run espera que tu aplicación
# escuche en el puerto especificado por la variable de entorno $PORT (por defecto 8080).
ENV PORT 8080
EXPOSE $PORT 
# Declara que este puerto será usado

# El comando que se ejecuta cuando el contenedor se inicia.
# Aquí le decimos que ejecute tu script 'app.py'.
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
