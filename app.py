from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import pyodbc
from datetime import datetime
from flask_cors import CORS 

# --- Configuración de la Aplicación y Conexión ---
app = Flask(__name__)
CORS(app) # <--- CORRECCIÓN 2: HABILITAMOS CORS para permitir llamadas desde el frontend local

# CADENA DE CONEXIÓN A SQL SERVER
# VERIFICA LAS CREDENCIALES FINALES
SQL_CONN_STR = (
    r'DRIVER={ODBC Driver 17 for SQL Server};'
    r'SERVER=THV;' 
    r'DATABASE=CitaMedDB;' 
    r'UID=sa;' 
    r'PWD=btspavedtheway;' 
)

def get_db_connection():
    """Conecta con la base de datos SQL Server. Lanza una excepción si falla."""
    try:
        conn = pyodbc.connect(SQL_CONN_STR)
        return conn
    except pyodbc.Error as ex:
        # En caso de error de conexión, imprime el error y relanza la excepción.
        print(f"Error crítico al conectar: {ex}")
        raise ConnectionError("Fallo en la conexión a la Base de Datos.")

def init_db():
    """Inicializa la base de datos y crea las tablas usando T-SQL."""
    conn = None # CORRECCIÓN 3: Inicializamos conn a None para evitar UnboundLocalError
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Creación de Tablas (T-SQL) - Esto crea las tablas Pacientes, Doctores y Citas
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Pacientes' AND xtype='U')
            CREATE TABLE Pacientes (
                id INT PRIMARY KEY IDENTITY(1,1),
                nombre NVARCHAR(100) NOT NULL,
                email NVARCHAR(100) UNIQUE NOT NULL,
                password_hash NVARCHAR(255) NOT NULL
            );

            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Doctores' AND xtype='U')
            CREATE TABLE Doctores (
                id INT PRIMARY KEY IDENTITY(1,1),
                nombre NVARCHAR(100) NOT NULL,
                especialidad NVARCHAR(100) NOT NULL
            );

            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Citas' AND xtype='U')
            CREATE TABLE Citas (
                id INT PRIMARY KEY IDENTITY(1,1),
                paciente_id INT NOT NULL,
                doctor_id INT NOT NULL,
                fecha_hora DATETIME NOT NULL,
                estado NVARCHAR(50) DEFAULT 'Pendiente',
                FOREIGN KEY (paciente_id) REFERENCES Pacientes (id),
                FOREIGN KEY (doctor_id) REFERENCES Doctores (id),
                UNIQUE (doctor_id, fecha_hora)
            );
        """)

        # Insertar doctor de prueba (ID 1)
        cursor.execute("""
            IF NOT EXISTS (SELECT id FROM Doctores WHERE id = 1)
                INSERT INTO Doctores (nombre, especialidad) VALUES ('Dr. Juan Pérez', 'Cardiología');
        """)
        
        conn.commit()
    except ConnectionError:
        # Si get_db_connection lanza error, lo manejamos limpiamente
        pass
    except Exception as e:
        print(f"Error al inicializar las tablas: {e}")
    finally:
        if conn:
            conn.close()

# Llama a la inicialización de la DB al inicio
init_db()

# --- Endpoints API ---

## 1. Registro de Pacientes (HU-01)
@app.route('/api/pacientes/registro', methods=['POST'])
def registro_paciente():
    data = request.get_json()
    nombre = data.get('nombre')
    email = data.get('email')
    password = data.get('password')

    if not all([nombre, email, password]):
        return jsonify({"mensaje": "Faltan datos requeridos"}), 400

    # RNF Seguridad: Hashing de contraseña
    password_hash = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Pacientes (nombre, email, password_hash) VALUES (?, ?, ?)", 
                       nombre, email, password_hash)
        conn.commit()
        # Criterio de Aceptación: Registro exitoso
        return jsonify({"mensaje": "Registro exitoso", "paciente": nombre}), 201
    except pyodbc.IntegrityError:
        # Criterio de Aceptación: Email duplicado
        return jsonify({"mensaje": "El email ya está registrado"}), 409
    finally:
        conn.close()

## 2. Login de Pacientes (HU-02)
@app.route('/api/pacientes/login', methods=['POST'])
def login_paciente():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    paciente = cursor.execute("SELECT id, password_hash FROM Pacientes WHERE email = ?", (email,)).fetchone()
    conn.close()

    if paciente and check_password_hash(paciente[1], password):
        # Criterio de Aceptación: Login exitoso
        return jsonify({"mensaje": "Login exitoso", "paciente_id": paciente[0]}), 200
    else:
        # Criterio de Aceptación: Credenciales inválidas
        return jsonify({"mensaje": "Email o contraseña incorrectos"}), 401

## 3. Agendar Cita (HU-07)
@app.route('/api/citas', methods=['POST'])
def agendar_cita():
    data = request.get_json()
    paciente_id = data.get('paciente_id')
    doctor_id = data.get('doctor_id')
    fecha_hora_str = data.get('fecha_hora') # Formato 'YYYY-MM-DD HH:MM:SS'

    if not all([paciente_id, doctor_id, fecha_hora_str]):
        return jsonify({"mensaje": "Faltan datos para la cita"}), 400
    
    try:
        # Convierte el string a objeto datetime para SQL Server
        fecha_hora_obj = datetime.strptime(fecha_hora_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return jsonify({"mensaje": "Formato de fecha/hora inválido. Use YYYY-MM-DD HH:MM:SS"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # T-SQL: Intentar insertar la cita
        cursor.execute("INSERT INTO Citas (paciente_id, doctor_id, fecha_hora) VALUES (?, ?, ?)",
                     paciente_id, doctor_id, fecha_hora_obj)
        conn.commit()
        
        # Criterio de Aceptación: Reserva exitosa
        return jsonify({"mensaje": "Cita agendada exitosamente"}), 201
    except pyodbc.IntegrityError:
        # Criterio de Aceptación: Horario duplicado
        return jsonify({"mensaje": "Ese horario ya está reservado con el doctor"}), 409
    except Exception as e:
        print(f"Error al agendar: {e}")
        return jsonify({"mensaje": "Error interno del servidor"}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    # Ejecuta el servidor Flask para grabar el video de demostración:
    app.run(debug=True)