"""Capa de datos: conexión y creacion de tablas.
Usa PostgreSQL si existe la variable de entorno DATABASE_URL (por ejemplo en Render).
Si no existe, usa un archivo SQLite local (control_qr.db) para desarrollo en el equipo."""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "control_qr.db")

DATABASE_URL = os.environ.get("DATABASE_URL")
USANDO_POSTGRES = bool(DATABASE_URL)

if USANDO_POSTGRES:
    import psycopg2
    import psycopg2.extras


def get_db():
    if USANDO_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    if USANDO_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                cedula TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL,
                telefono TEXT,
                marca_equipo TEXT NOT NULL,
                color_equipo TEXT NOT NULL,
                qr_uuid TEXT UNIQUE NOT NULL,
                fecha_registro TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bitacora (
                id SERIAL PRIMARY KEY,
                usuario_id INTEGER NOT NULL REFERENCES usuarios (id),
                tipo TEXT NOT NULL,
                fecha_hora TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cuentas (
                id SERIAL PRIMARY KEY,
                usuario TEXT UNIQUE NOT NULL,
                clave_hash TEXT NOT NULL,
                rol TEXT NOT NULL,
                usuario_id INTEGER REFERENCES usuarios (id)
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cedula TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL,
                telefono TEXT,
                marca_equipo TEXT NOT NULL,
                color_equipo TEXT NOT NULL,
                qr_uuid TEXT UNIQUE NOT NULL,
                fecha_registro TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bitacora (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                fecha_hora TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cuentas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                clave_hash TEXT NOT NULL,
                rol TEXT NOT NULL,
                usuario_id INTEGER,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        """)

    conn.commit()
    cur.close()
    conn.close()
