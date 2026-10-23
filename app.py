"""
Control QR - Punto de arranque (arquitectura en tres capas)

  presentacion/  rutas de Flask + templates/ + static/   (lo que ve el usuario)
  logica/        servicios con las reglas del sistema    (login, registro, escaneo, estadísticas)
  datos/         conexión y consultas SQL                (base de datos)

Perfiles: guardia (Guardia / Colaborador) y estudiante.
"""
import os

from flask import Flask

from datos.db import init_db
from logica import servicios
from presentacion.rutas import registrar_rutas

app = Flask(__name__)

# Render define la variable RENDER; en tu equipo no existe.
EN_PRODUCCION = bool(os.environ.get("RENDER"))
clave_secreta = os.environ.get("SECRET_KEY")
if EN_PRODUCCION and not clave_secreta:
    raise RuntimeError("Falta la variable de entorno SECRET_KEY en producción.")
app.secret_key = clave_secreta or "dev-cambiar-en-produccion"

# Cookie de sesión: no legible por JavaScript, y solo por HTTPS cuando está publicada.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=EN_PRODUCCION,
)

init_db()
servicios.crear_guardia_inicial()
registrar_rutas(app)

if __name__ == "__main__":
    # debug=False para la demo: evita mostrar el traceback completo si algo falla.
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode)
