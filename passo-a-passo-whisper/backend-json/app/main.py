from typing import Optional, Union
from fastapi import FastAPI, File, UploadFile
import whisper
import os
import shutil
import json
from pydantic import BaseModel

app = FastAPI()

print("Carregando modelo de IA (Whisper)...")
model = whisper.load_model("base")
print("Modelo carregado!")

@app.get("/")
def diz_ola():
    return {"Olá": "Mundo."}

@app.post("/transcrever")
async def transcrever_audio(file: UploadFile = File(...)):
    caminho_temp = f"temp_{file.filename}"
    with open(caminho_temp, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        resultado = model.transcribe(caminho_temp, language="pt")
        text = resultado["text"].strip()
    finally:
        if os.path.exists(caminho_temp):
            os.remove(caminho_temp)
    return {"texto": text}

