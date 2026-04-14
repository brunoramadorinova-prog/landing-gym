from flask import Flask, request, jsonify
from flask_cors import CORS
import bcrypt
import jwt
import mercadopago
import smtplib
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from conexion_db import get_conexion
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
CORS(app)

GOOGLE_CLIENT_ID = "949176060922-9itlaonlmrk6rks01m8dgdd1c850s3c1.apps.googleusercontent.com"
SECRET_KEY = "atlas-gym-clave-super-secreta-2026"
MP_ACCESS_TOKEN = "APP_USR-1144455658682984-041118-52d2cb98e4471f3609166835746e9c46-604493130"

EMAIL_REMITENTE = "bruno.ramadori.nova@gmail.com"
EMAIL_PASSWORD  = "jlun npsd jhnd zgea"
URL_FRONTEND    = URL_FRONTEND = "https://brunoramadorinova-prog.github.io/landing-gym"

MEMBRESIAS = {
    "limitado": {
        "titulo":      "Pase Limitado",
        "descripcion": "Hasta 2 clases por semana de cualquier disciplina",
        "precio":      1
    },
    "libre": {
        "titulo":      "Pase Libre",
        "descripcion": "Clases ilimitadas en todas las disciplinas",
        "precio":      2
    }
}

DIAS_ES = {
    "Monday":    "Lunes",
    "Tuesday":   "Martes",
    "Wednesday": "Miércoles",
    "Thursday":  "Jueves",
    "Friday":    "Viernes",
    "Saturday":  "Sábado",
    "Sunday":    "Domingo"
}

def dia_hoy():
    return DIAS_ES.get(datetime.now().strftime("%A"), "")

def hora_fin_pasada(horario_str):
    try:
        hora_fin_str = horario_str.split("-")[1].strip()
        hora_fin = datetime.strptime(hora_fin_str, "%H:%M").replace(
            year=datetime.now().year,
            month=datetime.now().month,
            day=datetime.now().day
        )
        return datetime.now() > hora_fin
    except:
        return False

def crear_token(nombre, rol):
    payload = {
        "nombre": nombre,
        "rol":    rol,
        "exp":    datetime.now(timezone.utc) + timedelta(hours=8)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verificar_token(token_str):
    try:
        payload = jwt.decode(token_str, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def obtener_inicio_semana():
    hoy = datetime.now().date()
    inicio = hoy - timedelta(days=hoy.weekday())
    return inicio

def enviar_email_verificacion(email_destino, nombre, token_verificacion):
    link = f"{URL_FRONTEND}/verificar-email.html?token={token_verificacion}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Verifica tu cuenta - Atlas Gym"
    msg["From"]    = EMAIL_REMITENTE
    msg["To"]      = email_destino

    texto_plano = f"""
Hola {nombre},

Gracias por registrarte en Atlas Gym.
Para activar tu cuenta hace click en el siguiente link:

{link}

Este link expira en 24 horas.

Si no te registraste en Atlas Gym, ignora este email.
    """

    texto_html = f"""
    <html>
    <body style="background:#121212; color:#ffffff; font-family: Arial, sans-serif; padding: 40px;">
        <div style="max-width: 500px; margin: 0 auto; background: #1a1a1a; border-radius: 8px; padding: 30px; border: 1px solid #333;">
            <h2 style="color: #d32f2f; text-align: center;">ATLAS GYM</h2>
            <h3 style="color: white;">Hola {nombre},</h3>
            <p style="color: #ccc;">
                Gracias por registrarte. Para activar tu cuenta y acceder al tatami,
                hace click en el boton de abajo.
            </p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{link}"
                   style="background: #d32f2f; color: white; padding: 14px 30px; border-radius: 5px; text-decoration: none; font-weight: bold; font-size: 16px;">
                    VERIFICAR MI CUENTA
                </a>
            </div>
            <p style="color: #666; font-size: 13px; text-align: center;">
                Este link expira en 24 horas.<br>
                Si no te registraste en Atlas Gym, ignora este email.
            </p>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(texto_plano, "plain"))
    msg.attach(MIMEText(texto_html,  "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
        servidor.login(EMAIL_REMITENTE, EMAIL_PASSWORD)
        servidor.sendmail(EMAIL_REMITENTE, email_destino, msg.as_string())


# --- REGISTRAR LUCHADOR ---
@app.route("/registrar-luchador", methods=["POST"])
def registrar_luchador():
    nombre   = request.form.get("nombre", "").strip()
    email    = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not nombre or not email or not password:
        return "Todos los campos son obligatorios.", 400

    con = get_conexion()
    if con is None:
        return "Error de conexión.", 500

    cursor = con.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
    if cursor.fetchone():
        con.close()
        return "Este email ya está registrado.", 409

    password_hash      = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    token_verificacion = secrets.token_urlsafe(32)
    expiracion         = datetime.now() + timedelta(hours=24)

    cursor.execute(
        """INSERT INTO usuarios 
           (nombre_completo, email, password_hash, rol, membresia, 
            email_verificado, token_verificacion, token_expiracion) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (nombre, email, password_hash, "USER", "sin_membresia",
         False, token_verificacion, expiracion)
    )
    con.commit()
    con.close()

    try:
        enviar_email_verificacion(email, nombre, token_verificacion)
    except Exception as e:
        print(f">>> [Error] No se pudo enviar el email: {e}")

    return "Registro exitoso. Revisá tu email para verificar tu cuenta.", 200


# --- VERIFICAR EMAIL ---
@app.route("/verificar-email", methods=["GET"])
def verificar_email():
    token = request.args.get("token")

    if not token:
        return "Token inválido.", 400

    con = get_conexion()
    if con is None:
        return "Error de conexión.", 500

    cursor = con.cursor()
    cursor.execute(
        "SELECT id, token_expiracion FROM usuarios WHERE token_verificacion = %s",
        (token,)
    )
    usuario = cursor.fetchone()

    if not usuario:
        con.close()
        return "Token inválido o ya usado.", 400

    if datetime.now() > usuario[1]:
        con.close()
        return "El link expiró. Registrate de nuevo.", 400

    cursor.execute(
        """UPDATE usuarios 
           SET email_verificado = True, token_verificacion = NULL, token_expiracion = NULL
           WHERE id = %s""",
        (usuario[0],)
    )
    con.commit()
    con.close()
    return "Email verificado exitosamente.", 200


# --- LOGIN TRADICIONAL ---
@app.route("/login", methods=["POST"])
def login():
    email    = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    con = get_conexion()
    if con is None:
        return "Error de conexión", 500

    cursor = con.cursor()
    cursor.execute(
        "SELECT nombre_completo, password_hash, rol, membresia, email_verificado FROM usuarios WHERE email = %s",
        (email,)
    )
    usuario = cursor.fetchone()
    con.close()

    if usuario and bcrypt.checkpw(password.encode("utf-8"), usuario[1].encode("utf-8")):
        if not usuario[4]:
            return "Verificá tu email antes de iniciar sesión.", 403

        nombre    = usuario[0]
        rol       = usuario[2]
        membresia = usuario[3]
        token     = crear_token(nombre, rol)
        return jsonify({
            "nombre":    nombre,
            "rol":       rol,
            "membresia": membresia,
            "token":     token
        })
    else:
        return "Credenciales incorrectas", 401


# --- LOGIN CON GOOGLE ---
@app.route("/login-google", methods=["POST"])
def login_google():
    datos        = request.get_json()
    token_google = datos.get("token")

    try:
        info          = id_token.verify_oauth2_token(token_google, google_requests.Request(), GOOGLE_CLIENT_ID)
        email         = info.get("email")
        nombre_google = info.get("name")
    except Exception as e:
        return f"Token de Google inválido: {e}", 401

    con = get_conexion()
    if con is None:
        return "Error de conexión", 500

    cursor = con.cursor()
    cursor.execute(
        "SELECT nombre_completo, rol, membresia FROM usuarios WHERE email = %s",
        (email,)
    )
    usuario = cursor.fetchone()

    if usuario is None:
        cursor.execute(
            """INSERT INTO usuarios 
               (email, nombre_completo, rol, password_hash, membresia, email_verificado) 
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (email, nombre_google, "USER", "", "sin_membresia", True)
        )
        con.commit()
        nombre    = nombre_google
        rol       = "USER"
        membresia = "sin_membresia"
    else:
        nombre    = usuario[0]
        rol       = usuario[1]
        membresia = usuario[2]

    con.close()

    token = crear_token(nombre, rol)
    return jsonify({
        "nombre":    nombre,
        "rol":       rol,
        "membresia": membresia,
        "token":     token
    })


# --- OBTENER MEMBRESIAS ---
@app.route("/membresias", methods=["GET"])
def obtener_membresias():
    return jsonify(MEMBRESIAS)


# --- CREAR PREFERENCIA DE PAGO ---
@app.route("/crear-pago", methods=["POST"])
def crear_pago():
    datos          = request.get_json()
    tipo_membresia = datos.get("tipo")
    nombre_alumno  = datos.get("nombre")

    if tipo_membresia not in MEMBRESIAS:
        return "Membresía inválida", 400

    membresia = MEMBRESIAS[tipo_membresia]
    sdk       = mercadopago.SDK(MP_ACCESS_TOKEN)

    preference_data = {
        "items": [{
            "title":       membresia["titulo"],
            "description": membresia["descripcion"],
            "quantity":    1,
            "unit_price":  membresia["precio"],
            "currency_id": "ARS"
        }],
        "payer":    {"name": nombre_alumno},
        "metadata": {
            "alumno":         nombre_alumno,
            "tipo_membresia": tipo_membresia
        },
        "back_urls": {
            "success": f"{URL_FRONTEND}/pago-exitoso.html",
            "failure": f"{URL_FRONTEND}/pago-fallido.html",
            "pending": f"{URL_FRONTEND}/pago-pendiente.html"
        }
        # ✅ auto_return removido — MP no lo acepta con URLs locales
        # Se vuelve a agregar cuando hagamos el deploy con URL real
    }

    resultado   = sdk.preference().create(preference_data)
    preferencia = resultado["response"]

    print(">>> [MP] Status:", resultado["status"])
    print(">>> [MP] Respuesta:", preferencia)

    if resultado["status"] == 201:
        return jsonify({"init_point": preferencia["init_point"]})
    else:
        return "Error al crear preferencia de pago", 500


# --- WEBHOOK DE MERCADOPAGO ---
@app.route("/webhook-mp", methods=["POST"])
def webhook_mp():
    datos = request.get_json()

    if datos.get("type") != "payment":
        return "OK", 200

    payment_id = datos.get("data", {}).get("id")
    if not payment_id:
        return "OK", 200

    sdk       = mercadopago.SDK(MP_ACCESS_TOKEN)
    pago      = sdk.payment().get(payment_id)
    info_pago = pago["response"]

    if info_pago.get("status") != "approved":
        return "OK", 200

    metadata       = info_pago.get("metadata", {})
    alumno         = metadata.get("alumno")
    tipo_membresia = metadata.get("tipo_membresia")

    if not alumno or not tipo_membresia:
        return "OK", 200

    con = get_conexion()
    if con is None:
        return "OK", 200

    cursor = con.cursor()
    cursor.execute(
        "UPDATE usuarios SET membresia = %s WHERE nombre_completo = %s",
        (tipo_membresia, alumno)
    )
    con.commit()
    con.close()
    return "OK", 200


# --- OBTENER HORARIOS ---
@app.route("/obtener-horarios", methods=["GET"])
def obtener_horarios():
    con = get_conexion()
    if con is None:
        return jsonify([])

    cursor = con.cursor()
    cursor.execute("SELECT id, dia, horario, disciplina, clase_tipo FROM horarios_clases")
    filas = cursor.fetchall()
    con.close()

    lista = []
    for fila in filas:
        lista.append({
            "id":         fila[0],
            "dia":        fila[1],
            "horario":    fila[2],
            "disciplina": fila[3],
            "clase_tipo": fila[4]
        })
    return jsonify(lista)


# --- AGREGAR CLASE ---
@app.route("/agregar-clase", methods=["POST"])
def agregar_clase():
    con = get_conexion()
    if con is None:
        return "Error de conexión", 500

    cursor = con.cursor()
    cursor.execute(
        "INSERT INTO horarios_clases (dia, horario, disciplina, clase_tipo) VALUES (%s, %s, %s, %s)",
        (
            request.form.get("dia"),
            request.form.get("horario"),
            request.form.get("disciplina"),
            request.form.get("clase_tipo")
        )
    )
    con.commit()
    con.close()
    return "Clase agregada correctamente."


# --- ELIMINAR CLASE ---
@app.route("/eliminar-clase", methods=["DELETE"])
def eliminar_clase():
    id_clase = request.args.get("id")

    con = get_conexion()
    if con is None:
        return "Error de conexión", 500

    cursor = con.cursor()
    cursor.execute("DELETE FROM horarios_clases WHERE id = %s", (id_clase,))
    filas_borradas = cursor.rowcount
    con.commit()
    con.close()

    if filas_borradas > 0:
        return "Clase eliminada."
    else:
        return "Clase no encontrada.", 404


# --- CERRAR CLASES PASADAS Y MARCAR AUSENTES ---
@app.route("/cerrar-clases-pasadas", methods=["POST"])
def cerrar_clases_pasadas():
    hoy       = dia_hoy()
    fecha_hoy = datetime.now().strftime("%d de %B").lower()

    con = get_conexion()
    if con is None:
        return "Error de conexión", 500

    cursor = con.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asistencias (
            id SERIAL PRIMARY KEY,
            alumno_nombre TEXT,
            dia TEXT,
            horario TEXT,
            disciplina TEXT,
            fecha TEXT,
            estado TEXT DEFAULT 'PRESENTE',
            fecha_registro TIMESTAMP DEFAULT NOW()
        )
    """)

    cursor.execute(
        "SELECT horario, disciplina FROM horarios_clases WHERE dia = %s", (hoy,)
    )
    clases_hoy           = cursor.fetchall()
    ausentes_registrados = 0

    for clase in clases_hoy:
        horario, disciplina = clase
        if not hora_fin_pasada(horario):
            continue

        cursor.execute(
            "SELECT alumno_nombre FROM reservas WHERE dia = %s AND horario = %s AND disciplina = %s",
            (hoy, horario, disciplina)
        )
        anotados = cursor.fetchall()

        for fila in anotados:
            alumno = fila[0]
            cursor.execute(
                """SELECT id FROM asistencias 
                   WHERE alumno_nombre = %s AND dia = %s AND horario = %s AND disciplina = %s""",
                (alumno, hoy, horario, disciplina)
            )
            ya_registrado = cursor.fetchone()

            if not ya_registrado:
                cursor.execute(
                    """INSERT INTO asistencias 
                       (alumno_nombre, dia, horario, disciplina, fecha, estado) 
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (alumno, hoy, horario, disciplina, fecha_hoy, "AUSENTE")
                )
                ausentes_registrados += 1

    con.commit()
    con.close()
    return jsonify({"ausentes_registrados": ausentes_registrados})


# --- TODAS LAS RESERVAS DE HOY ---
@app.route("/todas-las-reservas", methods=["GET"])
def todas_las_reservas():
    hoy = dia_hoy()

    con = get_conexion()
    if con is None:
        return jsonify([])

    cursor = con.cursor()
    cursor.execute(
        "SELECT alumno_nombre, dia, horario, disciplina, fecha FROM reservas WHERE dia = %s",
        (hoy,)
    )
    filas = cursor.fetchall()
    con.close()

    lista = []
    for fila in filas:
        lista.append({
            "alumno":     fila[0],
            "dia":        fila[1],
            "horario":    fila[2],
            "disciplina": fila[3],
            "fecha":      fila[4]
        })
    return jsonify(lista)


# --- MARCAR ASISTENCIA ---
@app.route("/marcar-asistencia", methods=["POST"])
def marcar_asistencia():
    con = get_conexion()
    if con is None:
        return "Error de conexión", 500

    alumno     = request.form.get("alumno")
    dia        = request.form.get("dia")
    horario    = request.form.get("horario")
    disciplina = request.form.get("disciplina")
    fecha      = request.form.get("fecha")

    cursor = con.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asistencias (
            id SERIAL PRIMARY KEY,
            alumno_nombre TEXT,
            dia TEXT,
            horario TEXT,
            disciplina TEXT,
            fecha TEXT,
            estado TEXT DEFAULT 'PRESENTE',
            fecha_registro TIMESTAMP DEFAULT NOW()
        )
    """)

    cursor.execute(
        """SELECT id FROM asistencias 
           WHERE alumno_nombre = %s AND dia = %s AND horario = %s AND disciplina = %s""",
        (alumno, dia, horario, disciplina)
    )
    ya_registrado = cursor.fetchone()

    if ya_registrado:
        con.close()
        return "Ya estaba registrado.", 200

    cursor.execute(
        """INSERT INTO asistencias 
           (alumno_nombre, dia, horario, disciplina, fecha, estado) 
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (alumno, dia, horario, disciplina, fecha, "PRESENTE")
    )
    con.commit()
    con.close()
    return "Asistencia registrada."


# --- HISTORIAL DEL ALUMNO ---
@app.route("/historial-alumno", methods=["GET"])
def historial_alumno():
    alumno = request.args.get("alumno")

    con = get_conexion()
    if con is None:
        return jsonify([])

    cursor = con.cursor()
    cursor.execute(
        """SELECT dia, horario, disciplina, fecha, estado 
           FROM asistencias 
           WHERE alumno_nombre = %s 
           ORDER BY fecha_registro DESC""",
        (alumno,)
    )
    filas = cursor.fetchall()
    con.close()

    lista = []
    for fila in filas:
        lista.append({
            "dia":        fila[0],
            "horario":    fila[1],
            "disciplina": fila[2],
            "fecha":      fila[3],
            "estado":     fila[4]
        })
    return jsonify(lista)


# --- LISTAR RESERVAS ---
def listar_reservas(alumno):
    con = get_conexion()
    if con is None:
        return []

    cursor = con.cursor()
    cursor.execute(
        "SELECT dia, horario, disciplina, fecha FROM reservas WHERE alumno_nombre = %s",
        (alumno,)
    )
    filas = cursor.fetchall()
    con.close()

    lista = []
    for fila in filas:
        lista.append({
            "dia":        fila[0],
            "horario":    fila[1],
            "disciplina": fila[2],
            "fecha":      fila[3]
        })
    return lista


@app.route("/chequear-reservas", methods=["GET"])
def chequear_reservas():
    alumno = request.args.get("alumno")
    return jsonify(listar_reservas(alumno))

@app.route("/mis-reservas", methods=["GET"])
def mis_reservas():
    alumno = request.args.get("alumno")
    return jsonify(listar_reservas(alumno))


# --- RESERVAR CLASE ---
@app.route("/reservar-clase", methods=["POST"])
def reservar_clase():
    alumno_nombre = request.form.get("alumno_nombre")

    con = get_conexion()
    if con is None:
        return "Error de conexión", 500

    cursor = con.cursor()
    cursor.execute(
        "SELECT membresia FROM usuarios WHERE nombre_completo = %s",
        (alumno_nombre,)
    )
    resultado = cursor.fetchone()
    membresia = resultado[0] if resultado else "sin_membresia"

    if membresia == "sin_membresia":
        con.close()
        return "Sin membresía. Adquirí un plan para reservar clases.", 403

    if membresia == "limitado":
        inicio_semana = obtener_inicio_semana()
        cursor.execute(
            """SELECT COUNT(*) FROM reservas 
               WHERE alumno_nombre = %s AND fecha_registro >= %s""",
            (alumno_nombre, inicio_semana)
        )
        cantidad = cursor.fetchone()[0]
        if cantidad >= 2:
            con.close()
            return "LIMITE_ALCANZADO", 403

    cursor.execute(
        "INSERT INTO reservas (alumno_nombre, dia, horario, disciplina, fecha) VALUES (%s, %s, %s, %s, %s)",
        (
            alumno_nombre,
            request.form.get("dia"),
            request.form.get("horario"),
            request.form.get("disciplina"),
            request.form.get("fecha")
        )
    )
    con.commit()
    con.close()
    return "Reserva confirmada."


# --- CANCELAR RESERVA ---
@app.route("/cancelar-reserva", methods=["DELETE"])
def cancelar_reserva():
    alumno     = request.args.get("alumno")
    dia        = request.args.get("dia")
    horario    = request.args.get("horario")
    disciplina = request.args.get("disciplina")

    con = get_conexion()
    if con is None:
        return "Error de conexión", 500

    cursor = con.cursor()
    cursor.execute(
        "DELETE FROM reservas WHERE alumno_nombre = %s AND dia = %s AND horario = %s AND disciplina = %s",
        (alumno, dia, horario, disciplina)
    )
    filas_borradas = cursor.rowcount
    con.commit()
    con.close()

    if filas_borradas > 0:
        return "Reserva cancelada."
    else:
        return "Reserva no encontrada.", 404


if __name__ == "__main__":
    app.run(port=7070, debug=True)