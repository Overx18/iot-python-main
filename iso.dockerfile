# Usa una imagen oficial de Python
FROM python:3.12

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos del proyecto
COPY . /app

# Instala las dependencias
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expón el puerto
EXPOSE 8080

# Comando para ejecutar la app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
