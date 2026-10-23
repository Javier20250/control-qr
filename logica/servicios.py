"""Capa de lógica de negocio: las reglas del sistema.
No conoce Flask (ni sesiones ni HTML) y no escribe SQL."""
import io
import os
import re
import uuid
from datetime import datetime, timedelta

import qrcode
from werkzeug.security import generate_password_hash, check_password_hash

from datos import repositorio as repo

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


# ---------------- Utilidades ----------------
def imagen_qr_png(qr_uuid):
    """Genera el QR al momento y devuelve los bytes del PNG (no se guarda ningún archivo,
    así funciona igual en servidores donde el disco es temporal, como Render)."""
    buffer = io.BytesIO()
    qrcode.make(qr_uuid).save(buffer)
    return buffer.getvalue()


# ---------------- Autenticación ----------------
def crear_guardia_inicial():
    """Crea la cuenta inicial del guardia si no existe (configurable por entorno)."""
    nombre = os.environ.get("GUARDIA_USER", "guardia")
    clave = os.environ.get("GUARDIA_PASS", "guardia123")
    if not repo.cuenta_por_usuario(nombre):
        repo.crear_cuenta(nombre, generate_password_hash(clave), "guardia")


def autenticar(usuario, clave, rol):
    """Devuelve la cuenta si usuario, contraseña y rol coinciden; si no, None."""
    cuenta = repo.cuenta_por_usuario_y_rol(usuario, rol)
    if cuenta and check_password_hash(cuenta["clave_hash"], clave):
        return cuenta
    return None


# ---------------- Estudiante ----------------
def registrar_estudiante(form, cuenta_id=None):
    """Registra el equipo y genera el QR.
    - Sin cuenta_id: también crea la cuenta (usuario y contraseña).
    - Con cuenta_id: enlaza el registro a la cuenta que ya inició sesión.
    Devuelve (visitante, cuenta, error)."""
    crea_cuenta = cuenta_id is None
    usuario = form.get("usuario", "").strip()
    clave = form.get("clave", "")

    if crea_cuenta:
        if not usuario or len(clave) < 8:
            return None, None, "Elige un usuario y una contraseña de al menos 8 caracteres."
        if repo.cuenta_por_usuario(usuario):
            return None, None, "Ese usuario ya existe. Elige otro."

    cedula = form.get("cedula", "").strip()
    nombre = form.get("nombre", "").strip()
    correo = form.get("correo", "").strip()
    telefono = form.get("telefono", "").strip()
    marca = form.get("marca", "").strip()
    color = form.get("color", "").strip()
    if not all([cedula, nombre, correo, marca, color]):
        return None, None, "Faltan campos obligatorios."
    if not re.fullmatch(r"[0-9]{5,15}", cedula):
        return None, None, "La cédula debe tener solo números (entre 5 y 15 dígitos)."
    if telefono and not re.fullmatch(r"[0-9]{7,15}", telefono):
        return None, None, "El teléfono debe tener solo números (entre 7 y 15 dígitos)."

    visitante = repo.visitante_por_cedula(cedula)
    if visitante is None:
        nuevo_uuid = str(uuid.uuid4())
        visitante = repo.crear_visitante(cedula, nombre, correo, telefono, marca, color,
                                         nuevo_uuid, datetime.now().isoformat())

    if repo.cuenta_de_visitante(visitante["id"]):
        return None, None, "Esa cédula ya tiene una cuenta. Inicia sesión."

    if crea_cuenta:
        nuevo = repo.crear_cuenta(usuario, generate_password_hash(clave), "estudiante",
                                  visitante["id"])
        cuenta = repo.cuenta_por_id(nuevo)
    else:
        repo.vincular_cuenta(cuenta_id, visitante["id"])
        cuenta = repo.cuenta_por_id(cuenta_id)
    return visitante, cuenta, None


def visitante_de_cuenta(visitante_id):
    """Registro de equipo de un estudiante (None si aún no se registra)."""
    return repo.visitante_por_id(visitante_id) if visitante_id else None


def consultar_qr_propio(visitante_id, cedula):
    """El estudiante solo puede consultar la cédula de su propio registro."""
    visitante = repo.visitante_por_cedula(cedula)
    if visitante and visitante["id"] == visitante_id:
        return visitante
    return None


def visitante_por_uuid(qr_uuid):
    return repo.visitante_por_uuid(qr_uuid)


# ---------------- Guardia ----------------
def consultar_por_cedula(cedula):
    return repo.visitante_por_cedula(cedula)


def registrar_escaneo(qr_uuid):
    """Alterna entrada/salida. Devuelve (resultado_dict, codigo_http)."""
    qr_uuid = (qr_uuid or "").strip()
    if not qr_uuid:
        return {"ok": False, "mensaje": "No se recibio ningun codigo."}, 400

    visitante = repo.visitante_por_uuid(qr_uuid)
    if not visitante:
        return {"ok": False, "mensaje": "Codigo QR no reconocido."}, 404

    nuevo_tipo = "salida" if repo.ultimo_tipo(visitante["id"]) == "entrada" else "entrada"
    ahora = datetime.now()
    repo.registrar_movimiento(visitante["id"], nuevo_tipo, ahora.isoformat())

    return {
        "ok": True,
        "tipo": nuevo_tipo,
        "nombre": visitante["nombre"],
        "equipo": f"{visitante['marca_equipo']} {visitante['color_equipo']}",
        "hora": ahora.strftime("%H:%M:%S"),
    }, 200


def bitacora_completa():
    return repo.movimientos()


def datos_panel_guardia():
    """Historial reciente y estadísticas del panel del guardia."""
    return repo.movimientos(limite=6), estadisticas()


def estadisticas():
    ahora = datetime.now()
    hoy = ahora.strftime("%Y-%m-%d")

    accesos_hoy = repo.contar_movimientos(hoy)
    total = repo.contar_movimientos()

    ultimo = repo.fecha_ultimo_movimiento()
    if ultimo:
        mins = int((ahora - datetime.fromisoformat(ultimo)).total_seconds() // 60)
        if mins < 1:
            ultimo_txt = "hace instantes"
        elif mins < 60:
            ultimo_txt = f"hace {mins} min"
        elif mins < 1440:
            ultimo_txt = f"hace {mins // 60} h"
        else:
            ultimo_txt = f"hace {mins // 1440} d"
    else:
        ultimo_txt = "sin registros"

    # Barras: últimos 7 días
    semana = []
    for i in range(6, -1, -1):
        d = ahora - timedelta(days=i)
        semana.append({"dia": DIAS[d.weekday()],
                       "n": repo.contar_movimientos(d.strftime("%Y-%m-%d"))})
    maximo = max([s["n"] for s in semana] + [1])
    for s in semana:
        s["alto"] = max(int(s["n"] / maximo * 100), 4)

    # Línea: accesos por hora de hoy (8:00 a 17:00)
    horas = [repo.contar_movimientos(f"{hoy}T{h:02d}") for h in range(8, 18)]
    mh = max(horas + [1])
    puntos = [(i * 160 / (len(horas) - 1), 45 - (v / mh) * 40) for i, v in enumerate(horas)]
    linea = " ".join(f"{x:.1f},{y:.1f}" for x, y in puntos)
    area = f"0,50 {linea} 160,50"

    return {"accesos_hoy": accesos_hoy, "total": total, "ultimo": ultimo_txt,
            "semana": semana, "linea": linea, "area": area}
