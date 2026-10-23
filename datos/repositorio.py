"""Capa de datos: todas las consultas SQL del sistema.
Las otras capas nunca escriben SQL; solo llaman a estas funciones.
Funciona tanto con PostgreSQL (si hay DATABASE_URL) como con SQLite local."""
from datos.db import get_db, USANDO_POSTGRES


def _marcador():
    # PostgreSQL usa %s como marcador de parametros, SQLite usa ?
    return "%s" if USANDO_POSTGRES else "?"


def _adaptar(sql):
    if USANDO_POSTGRES:
        return sql.replace("?", "%s")
    return sql


def _uno(sql, params=()):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(_adaptar(sql), params)
        fila = cur.fetchone()
        cur.close()
        return fila
    finally:
        conn.close()


def _todos(sql, params=()):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(_adaptar(sql), params)
        filas = cur.fetchall()
        cur.close()
        return filas
    finally:
        conn.close()


def _escribir(sql, params=(), devolver_id=False):
    conn = get_db()
    try:
        cur = conn.cursor()
        if devolver_id and USANDO_POSTGRES:
            sql = sql + " RETURNING id"
            cur.execute(_adaptar(sql), params)
            nuevo_id = cur.fetchone()["id"]
        else:
            cur.execute(_adaptar(sql), params)
            nuevo_id = cur.lastrowid if not USANDO_POSTGRES else None
        conn.commit()
        cur.close()
        return nuevo_id
    finally:
        conn.close()


# ---------------- Cuentas (login) ----------------
def cuenta_por_usuario_y_rol(usuario, rol):
    return _uno("SELECT * FROM cuentas WHERE usuario = ? AND rol = ?", (usuario, rol))


def cuenta_por_usuario(usuario):
    return _uno("SELECT * FROM cuentas WHERE usuario = ?", (usuario,))


def cuenta_por_id(cuenta_id):
    return _uno("SELECT * FROM cuentas WHERE id = ?", (cuenta_id,))


def cuenta_de_visitante(visitante_id):
    return _uno("SELECT * FROM cuentas WHERE usuario_id = ?", (visitante_id,))


def crear_cuenta(usuario, clave_hash, rol, visitante_id=None):
    return _escribir(
        "INSERT INTO cuentas (usuario, clave_hash, rol, usuario_id) VALUES (?, ?, ?, ?)",
        (usuario, clave_hash, rol, visitante_id),
        devolver_id=True,
    )


def vincular_cuenta(cuenta_id, visitante_id):
    _escribir("UPDATE cuentas SET usuario_id = ? WHERE id = ?", (visitante_id, cuenta_id))


# ---------------- Visitantes ----------------
def visitante_por_cedula(cedula):
    return _uno("SELECT * FROM usuarios WHERE cedula = ?", (cedula,))


def visitante_por_uuid(qr_uuid):
    return _uno("SELECT * FROM usuarios WHERE qr_uuid = ?", (qr_uuid,))


def visitante_por_id(visitante_id):
    return _uno("SELECT * FROM usuarios WHERE id = ?", (visitante_id,))


def crear_visitante(cedula, nombre, correo, telefono, marca, color, qr_uuid, fecha):
    nuevo_id = _escribir(
        """INSERT INTO usuarios
           (cedula, nombre, correo, telefono, marca_equipo, color_equipo, qr_uuid, fecha_registro)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (cedula, nombre, correo, telefono, marca, color, qr_uuid, fecha),
        devolver_id=True,
    )
    if nuevo_id is None:
        # SQLite: buscar el recien creado por qr_uuid (es unico)
        return visitante_por_uuid(qr_uuid)
    return visitante_por_id(nuevo_id)


# ---------------- Bitacora ----------------
def ultimo_tipo(visitante_id):
    fila = _uno(
        "SELECT tipo FROM bitacora WHERE usuario_id = ? ORDER BY id DESC LIMIT 1",
        (visitante_id,),
    )
    return fila["tipo"] if fila else None


def registrar_movimiento(visitante_id, tipo, fecha_hora):
    _escribir(
        "INSERT INTO bitacora (usuario_id, tipo, fecha_hora) VALUES (?, ?, ?)",
        (visitante_id, tipo, fecha_hora),
    )


def movimientos(limite=None):
    sql = """
        SELECT b.tipo, b.fecha_hora, u.nombre, u.marca_equipo, u.color_equipo
        FROM bitacora b JOIN usuarios u ON u.id = b.usuario_id
        ORDER BY b.id DESC
    """
    if limite:
        return _todos(sql + " LIMIT ?", (limite,))
    return _todos(sql)


def contar_movimientos(prefijo_fecha=None):
    if prefijo_fecha:
        fila = _uno("SELECT COUNT(*) AS total FROM bitacora WHERE fecha_hora LIKE ?",
                    (prefijo_fecha + "%",))
    else:
        fila = _uno("SELECT COUNT(*) AS total FROM bitacora")
    return fila["total"]


def fecha_ultimo_movimiento():
    fila = _uno("SELECT fecha_hora FROM bitacora ORDER BY id DESC LIMIT 1")
    return fila["fecha_hora"] if fila else None
