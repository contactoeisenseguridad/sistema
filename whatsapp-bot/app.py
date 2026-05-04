from fastapi import FastAPI
from pydantic import BaseModel
from respuestas_base import responder_mensaje

app = FastAPI()


class MensajeEntrada(BaseModel):
    mensaje: str


@app.get("/")
def inicio():
    return {
        "estado": "Bot OTEC UNO funcionando correctamente"
    }


@app.post("/webhook")
def webhook(data: MensajeEntrada):
    respuesta = responder_mensaje(data.mensaje)

    return {
        "mensaje_recibido": data.mensaje,
        "respuesta": respuesta
    }