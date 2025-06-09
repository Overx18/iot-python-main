from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from lpr_model import detectar_placa
import uvicorn

app = FastAPI()

@app.post("/lpr")
async def procesar_placa(file: UploadFile = File(...)):
    contents = await file.read()
    placa = detectar_placa(contents)
    return JSONResponse(content={"numero_placa": placa})