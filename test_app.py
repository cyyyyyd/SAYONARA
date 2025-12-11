import pytest
import pyodbc
from app import app, init_db, get_db_connection, SQL_CONN_STR
from datetime import datetime


app.config['TESTING'] = True

def clear_tables_sql_server():
    """Limpia los datos de las tablas de Pacientes y Citas."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Limpieza en orden por las Foreign Keys
    cursor.execute("DELETE FROM Citas")
    cursor.execute("DELETE FROM Pacientes")
    conn.commit()
    conn.close()

@pytest.fixture
def client():
    """Configura el cliente de prueba de Flask y asegura la DB limpia."""
    
    # Aseguramos que las tablas existan al inicio de la suite de pruebas
    init_db() 
    
    # Limpieza antes de cada prueba
    clear_tables_sql_server()

    with app.test_client() as client:
        yield client

    # Limpieza después de cada prueba (para mayor seguridad)
    clear_tables_sql_server()

# --- Casos de Prueba Unitarios/Funcionales ---

def test_registro_paciente_exitoso(client):
    """Verifica HU-01: Registro exitoso. Criterio: Respuesta 201 (Created)."""
    response = client.post('/api/pacientes/registro', json={
        'nombre': 'Test Patient',
        'email': 'test@example.com',
        'password': 'Password123'
    })
    assert response.status_code == 201
    assert response.get_json()['mensaje'] == 'Registro exitoso'

def test_registro_paciente_email_duplicado(client):
    """Verifica HU-01: No permite email duplicado. Criterio: Respuesta 409 (Conflict)."""
    # Primer registro exitoso
    client.post('/api/pacientes/registro', json={
        'nombre': 'Duplicate User',
        'email': 'duplicate@test.com',
        'password': 'Password123'
    })
    # Segundo registro (debe fallar)
    response = client.post('/api/pacientes/registro', json={
        'nombre': 'Another User',
        'email': 'duplicate@test.com',
        'password': 'Password456'
    })
    assert response.status_code == 409
    assert response.get_json()['mensaje'] == 'El email ya está registrado'

def test_login_paciente_exitoso(client):
    """Verifica HU-02: Login con credenciales correctas. Criterio: Respuesta 200 (OK)."""
    # Precondición: Registrar un paciente
    client.post('/api/pacientes/registro', json={
        'nombre': 'Login User',
        'email': 'login@test.com',
        'password': 'SecurePass'
    })

    # Ejecutar login
    response = client.post('/api/pacientes/login', json={
        'email': 'login@test.com',
        'password': 'SecurePass'
    })
    assert response.status_code == 200
    assert response.get_json()['mensaje'] == 'Login exitoso'

def test_login_paciente_fallido(client):
    """Verifica HU-02: Login con contraseña incorrecta. Criterio: Respuesta 401 (Unauthorized)."""
    # Precondición: Registrar un paciente
    client.post('/api/pacientes/registro', json={
        'nombre': 'Fail Login',
        'email': 'fail@test.com',
        'password': 'RightPass'
    })

    # Ejecutar login con contraseña incorrecta
    response = client.post('/api/pacientes/login', json={
        'email': 'fail@test.com',
        'password': 'WrongPass'
    })
    assert response.status_code == 401
    assert response.get_json()['mensaje'] == 'Email o contraseña incorrectos'

def test_agendar_cita_exitoso(client):
    """Verifica HU-07: Agendamiento de cita. Criterio: Respuesta 201 (Created)."""
    # Precondición: Registrar paciente
    client.post('/api/pacientes/registro', json={'nombre': 'Cita User', 'email': 'cita@test.com', 'password': 'pass'})
    
    # Obtener el ID del paciente recién creado
    conn = get_db_connection()
    cursor = conn.cursor()
    paciente_id = cursor.execute("SELECT id FROM Pacientes WHERE email = 'cita@test.com'").fetchone()[0]
    conn.close()

    fecha_cita = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    response = client.post('/api/citas', json={
        'paciente_id': paciente_id,
        'doctor_id': 1, # ID del doctor de prueba insertado en init_db
        'fecha_hora': fecha_cita
    })

    assert response.status_code == 201
    assert response.get_json()['mensaje'] == 'Cita agendada exitosamente'

def test_agendar_cita_horario_duplicado(client):
    """Verifica HU-07: No permite agendar 2 citas al mismo doctor a la misma hora. Criterio: 409 (Conflict)."""
    # Precondición: Registrar 2 pacientes
    client.post('/api/pacientes/registro', json={'nombre': 'P1', 'email': 'p1@test.com', 'password': 'pass'})
    client.post('/api/pacientes/registro', json={'nombre': 'P2', 'email': 'p2@test.com', 'password': 'pass'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    p1_id = cursor.execute("SELECT id FROM Pacientes WHERE email = 'p1@test.com'").fetchone()[0]
    p2_id = cursor.execute("SELECT id FROM Pacientes WHERE email = 'p2@test.com'").fetchone()[0]
    conn.close()

    fecha_conflicto = '2026-01-01 11:00:00'

    # Primera cita (Debe ser exitosa)
    client.post('/api/citas', json={
        'paciente_id': p1_id,
        'doctor_id': 1,
        'fecha_hora': fecha_conflicto
    })

    # Segunda cita (Debe fallar)
    response = client.post('/api/citas', json={
        'paciente_id': p2_id,
        'doctor_id': 1,
        'fecha_hora': fecha_conflicto
    })

    assert response.status_code == 409
    assert response.get_json()['mensaje'] == 'Ese horario ya está reservado con el doctor'