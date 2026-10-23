"""Capa de presentación: rutas de Flask, sesión y plantillas.
Solo recibe la petición, llama a la capa de lógica y devuelve la pantalla."""
from functools import wraps

from flask import (render_template, request, redirect, url_for,
                   jsonify, session, Response)

from logica import servicios

ROLES = {
    "guardia": {"etiqueta": "Guardia / Colaborador", "panel": "panel_guardia"},
    "estudiante": {"etiqueta": "Estudiante", "panel": "panel_estudiante"},
}


def requiere_rol(rol, api=False):
    """Protege una ruta: solo entra quien inició sesión con ese rol."""
    def decorador(f):
        @wraps(f)
        def envoltura(*args, **kwargs):
            if session.get("rol") != rol:
                if api:
                    return jsonify({"ok": False, "mensaje": "Sesión no válida."}), 401
                return redirect(url_for("login", rol=rol))
            return f(*args, **kwargs)
        return envoltura
    return decorador


def requiere_sesion(f):
    @wraps(f)
    def envoltura(*args, **kwargs):
        if not session.get("rol"):
            return redirect(url_for("inicio"))
        return f(*args, **kwargs)
    return envoltura


def iniciar_sesion(cuenta):
    session.clear()
    session["cuenta_id"] = cuenta["id"]
    session["rol"] = cuenta["rol"]
    session["usuario_id"] = cuenta["usuario_id"]
    session["nombre_cuenta"] = cuenta["usuario"]


def registrar_rutas(app):

    @app.context_processor
    def datos_globales():
        rol = session.get("rol")
        panel = url_for(ROLES[rol]["panel"]) if rol in ROLES else url_for("inicio")
        return {"rol_actual": rol, "panel_url": panel}

    # ----------------- Inicio, login y logout -----------------
    @app.route("/")
    def inicio():
        rol = session.get("rol")
        if rol in ROLES:
            return redirect(url_for(ROLES[rol]["panel"]))
        return render_template("index.html")

    @app.route("/login/<rol>", methods=["GET", "POST"])
    def login(rol):
        if rol not in ROLES:
            return redirect(url_for("inicio"))
        error = None
        if request.method == "POST":
            cuenta = servicios.autenticar(request.form.get("usuario", "").strip(),
                                          request.form.get("clave", ""), rol)
            if cuenta:
                iniciar_sesion(cuenta)
                return redirect(url_for(ROLES[rol]["panel"]))
            error = "Usuario o contraseña incorrectos."
        return render_template("login.html", rol=rol,
                               etiqueta=ROLES[rol]["etiqueta"], error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("inicio"))

    # ----------------- Estudiante -----------------
    @app.route("/estudiante")
    @requiere_rol("estudiante")
    def panel_estudiante():
        return render_template("estudiante.html")

    @app.route("/registro", methods=["GET", "POST"])
    def registro():
        rol = session.get("rol")
        if rol == "guardia":
            return redirect(url_for("panel_guardia"))

        # Estudiante con sesión que ya tiene su registro: va directo a su QR
        if rol == "estudiante":
            propio = servicios.visitante_de_cuenta(session.get("usuario_id"))
            if propio:
                return redirect(url_for("ver_qr", qr_uuid=propio["qr_uuid"]))

        crea_cuenta = rol != "estudiante"
        if request.method == "GET":
            return render_template("registro.html", error=None,
                                   crea_cuenta=crea_cuenta, modo="estudiante")

        visitante, cuenta, error = servicios.registrar_estudiante(
            request.form, cuenta_id=None if crea_cuenta else session["cuenta_id"])
        if error:
            return render_template("registro.html", error=error,
                                   crea_cuenta=crea_cuenta, modo="estudiante")

        if crea_cuenta:
            iniciar_sesion(cuenta)
        else:
            session["usuario_id"] = visitante["id"]
        return redirect(url_for("ver_qr", qr_uuid=visitante["qr_uuid"]))

    @app.route("/mi-qr", methods=["GET", "POST"])
    @requiere_rol("estudiante")
    def mi_qr():
        """Ya tengo mi QR: si ya tiene un registro (sesión con usuario_id), va
        directo a su código. Si aun no se ha registrado, pide la cedula para
        buscarlo (por ejemplo si creo la cuenta pero no alcanzo a terminar el
        registro del equipo)."""
        if session.get("usuario_id"):
            usuario = servicios.visitante_de_cuenta(session["usuario_id"])
            if usuario:
                return redirect(url_for("ver_qr", qr_uuid=usuario["qr_uuid"]))

        if request.method == "GET":
            return render_template("buscar_qr.html", error=None, usuario=None, cedula="")

        cedula = request.form.get("cedula", "").strip()
        usuario = servicios.consultar_qr_propio(session.get("usuario_id"), cedula)
        if not usuario:
            return render_template("buscar_qr.html", usuario=None, cedula=cedula,
                                   error="No encontramos un registro tuyo con esa cédula.")
        return render_template("buscar_qr.html", error=None, usuario=usuario, cedula=cedula)

    @app.route("/qr/<qr_uuid>")
    @requiere_sesion
    def ver_qr(qr_uuid):
        usuario = servicios.visitante_por_uuid(qr_uuid)
        if not usuario:
            return "QR no encontrado", 404
        # Un estudiante solo puede ver su propio QR
        if session["rol"] == "estudiante" and session.get("usuario_id") != usuario["id"]:
            return redirect(url_for("panel_estudiante"))
        return render_template("qr.html", usuario=usuario)

    @app.route("/qr-img/<qr_uuid>.png")
    @requiere_sesion
    def imagen_qr(qr_uuid):
        """Imagen del QR generada al momento. El estudiante solo ve la suya."""
        usuario = servicios.visitante_por_uuid(qr_uuid)
        if not usuario:
            return "QR no encontrado", 404
        if session["rol"] == "estudiante" and session.get("usuario_id") != usuario["id"]:
            return "No autorizado", 403
        return Response(servicios.imagen_qr_png(qr_uuid), mimetype="image/png",
                        headers={"Cache-Control": "private, max-age=3600"})

    # ----------------- Guardia / Colaborador -----------------
    @app.route("/guardia")
    @requiere_rol("guardia")
    def panel_guardia():
        recientes, stats = servicios.datos_panel_guardia()
        return render_template("guardia.html", recientes=recientes, stats=stats)

    @app.route("/guardia/escanear")
    @requiere_rol("guardia")
    def escaneo():
        return render_template("escaneo.html")

    @app.route("/guardia/bitacora")
    @requiere_rol("guardia")
    def bitacora():
        return render_template("bitacora.html", movimientos=servicios.bitacora_completa())

    @app.route("/guardia/consultar", methods=["GET", "POST"])
    @requiere_rol("guardia")
    def consultar_qr():
        if request.method == "GET":
            return render_template("consultar.html", error=None)
        usuario = servicios.consultar_por_cedula(request.form.get("cedula", "").strip())
        if not usuario:
            return render_template("consultar.html", error="No hay un registro con esa cédula.")
        return redirect(url_for("ver_qr", qr_uuid=usuario["qr_uuid"]))

    # ----------------- API del escáner -----------------
    @app.route("/api/escanear", methods=["POST"])
    @requiere_rol("guardia", api=True)
    def api_escanear():
        data = request.get_json(silent=True) or {}
        resultado, codigo = servicios.registrar_escaneo(data.get("uuid", ""))
        return jsonify(resultado), codigo
