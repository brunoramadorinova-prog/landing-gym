from flask import Flask, request, jsonify
from flask_cors import CORS
import bcrypt
from conexion_db import get_conexion
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

GOOGLE_CLIENT_ID = "949176060922-9itlaonlmrk6rks01m8dgdd1c850s3c1.apps.googleusercontent.com"

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
    """Recibe '18:00 - 19:30' y devuelve True si la hora de fin ya pasó"""
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


# --- LOGIN TRADICIONAL ---
@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    con = get_conexion()
    if con is None:
        return "Error de conexión", 500

    cursor = con.cursor()
    cursor.execute(
        "SELECT nombre_completo, password_hash, rol FROM usuarios WHERE email = %s",
        (email,)
    )
    usuario = cursor.fetchone()
    con.close()

    if usuario and bcrypt.checkpw(password.encode("utf-8"), usuario[1].encode("utf-8")):
        return jsonify({
            "nombre": usuario[0],
            "rol":    usuario[2],
            "token":  "fake-jwt-token-para-" + usuario[0]
        })
    else:
        return "Credenciales incorrectas", 401


# --- LOGIN CON GOOGLE ---
@app.route("/login-google", methods=["POST"])
def login_google():
    datos = request.get_json()
    token = datos.get("token")

    try:
        info = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        email = info.get("email")
        nombre_google = info.get("name")
    except Exception as e:
        return f"Token de Google inválido: {e}", 401

    con = get_conexion()
    if con is None:
        return "Error de conexión", 500

    cursor = con.cursor()
    cursor.execute(
        "SELECT nombre_completo, rol FROM usuarios WHERE email = %s",
        (email,)
    )
    usuario = cursor.fetchone()

    if usuario is None:
        cursor.execute(
            "INSERT INTO usuarios (email, nombre_completo, rol, password_hash) VALUES (%s, %s, %s, %s)",
            (email, nombre_google, "USER", "")
        )
        con.commit()
        nombre = nombre_google
        rol = "USER"
    else:
        nombre = usuario[0]
        rol = usuario[1]

    con.close()

    return jsonify({
        "nombre": nombre,
        "rol":    rol,
        "token":  "fake-jwt-token-para-" + nombre
    })


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
    hoy = dia_hoy()
    fecha_hoy = datetime.now().strftime("%d de %B").lower()

    con = get_conexion()
    if con is None:
        return "Error de conexión", 500

    cursor = con.cursor()

    # Aseguramos que existe la tabla asistencias
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

    # Traemos todas las clases de hoy
    cursor.execute(
        "SELECT horario, disciplina FROM horarios_clases WHERE dia = %s",
        (hoy,)
    )
    clases_hoy = cursor.fetchall()

    ausentes_registrados = 0

    for clase in clases_hoy:
        horario, disciplina = clase

        # Solo procesamos clases cuya hora de fin ya pasó
        if not hora_fin_pasada(horario):
            continue

        # Buscamos alumnos anotados a esta clase hoy
        cursor.execute(
            "SELECT alumno_nombre FROM reservas WHERE dia = %s AND horario = %s AND disciplina = %s",
            (hoy, horario, disciplina)
        )
        anotados = cursor.fetchall()

        for fila in anotados:
            alumno = fila[0]

            # Verificamos si ya fue marcado PRESENTE o AUSENTE
            cursor.execute(
                """SELECT id FROM asistencias 
                   WHERE alumno_nombre = %s AND dia = %s AND horario = %s AND disciplina = %s""",
                (alumno, hoy, horario, disciplina)
            )
            ya_registrado = cursor.fetchone()

            if not ya_registrado:
                # No fue marcado PRESENTE, lo registramos como AUSENTE
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

    # Verificamos que no esté ya registrado
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
    con = get_conexion()
    if con is None:
        return "Error de conexión", 500

    cursor = con.cursor()
    cursor.execute(
        "INSERT INTO reservas (alumno_nombre, dia, horario, disciplina, fecha) VALUES (%s, %s, %s, %s, %s)",
        (
            request.form.get("alumno_nombre"),
            request.form.get("dia"),
            request.form.get("horario"),
            request.form.get("disciplina"),
            request.form.get("fecha")
        )
    )
    con.commit()
    con.close()
    return "¡Reserva confirmada!"


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