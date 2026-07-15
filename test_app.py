import unittest
from datetime import date, time
from app import app, db, User, Appointment

class PodologiaWebTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test_secret'
        self.client = app.test_client()

        with app.app_context():
            db.create_all()
            # Crear podólogo de prueba
            podo = User(email='podologo@test.com', full_name='Dr. Test', role='podologist')
            podo.set_password('admin')
            db.session.add(podo)

            # Crear paciente de prueba
            patient = User(email='paciente@test.com', full_name='Juan Test', role='patient', custom_price=30.0)
            patient.set_password('user')
            db.session.add(patient)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_login_page_loads(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('Iniciar Sesión', html)

    def test_registration_page_loads(self):
        response = self.client.get('/register')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('Registro de Paciente', html)

    def test_public_booking_page_loads(self):
        response = self.client.get('/reservar')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('Solicitud de Cita', html)

    def test_authentication_flow(self):
        # Intentar login con credenciales correctas
        response = self.client.post('/login', data={
            'email': 'podologo@test.com',
            'password': 'admin'
        })
        # Debe redirigir al calendario del podólogo
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/calendar') or response.location.endswith('/'))

        # Cerrar sesión para limpiar el estado autenticado
        self.client.get('/logout', follow_redirects=True)

        # Intentar login con credenciales incorrectas
        response = self.client.post('/login', data={
            'email': 'podologo@test.com',
            'password': 'wrong_password'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('incorrectos', html)

    def test_create_home_visit_appointment_by_patient(self):
        # Simular sesión de paciente
        self.client.post('/login', data={
            'email': 'paciente@test.com',
            'password': 'user'
        })

        # Agendar cita a domicilio
        response = self.client.post('/reservar', data={
            'date': '2026-10-15',
            'time': '10:00',
            'reason': 'Servicio domiciliario por uña encarnada',
            'is_home_visit': 'on',
            'home_address': 'Calle del Sol 456, Piso 4B'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        # Comprobar que en su portal se muestre la cita y que es a domicilio con su dirección
        self.assertIn('Calle del Sol 456, Piso 4B', html)
        self.assertIn('A domicilio', html)

        # Estricta Privacidad Financiera: asegurar que NUNCA aparezca custom_price ni info de precios
        self.assertNotIn('30.00', html)
        self.assertNotIn('30.0', html)

    def test_create_and_edit_appointment_duration_by_podologist(self):
        # Iniciar sesión de podólogo
        self.client.post('/login', data={
            'email': 'podologo@test.com',
            'password': 'admin'
        })

        # Agendar cita manual con duración personalizada (ej. 90 minutos para bloqueo)
        response = self.client.post('/api/appointments', json={
            'patient_id': 2, # El ID del paciente Juan Test
            'date': '2026-10-16',
            'time': '11:00',
            'reason': 'Consulta premium y masaje',
            'is_home_visit': True,
            'home_address': 'Av. de la Constitución 12',
            'duration_minutes': 90,
            'status': 'approved'
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        appt_id = data['appointment_id']

        # Verificar que el cálculo del bloqueo de calendario (GET) refleje los 90 minutos
        response = self.client.get('/api/appointments?start=2026-10-10T00:00:00Z&end=2026-10-20T00:00:00Z')
        self.assertEqual(response.status_code, 200)
        events = response.get_json()

        # Buscar el evento creado
        event = next((e for e in events if e['id'] == appt_id), None)
        self.assertIsNotNone(event)
        # Comprobar hora de inicio y de fin (11:00 a 12:30 -> 90 minutos)
        self.assertIn('11:00:00', event['start'])
        self.assertIn('12:30:00', event['end'])
        self.assertEqual(event['extendedProps']['duration_minutes'], 90)
        self.assertTrue(event['extendedProps']['is_home_visit'])
        self.assertEqual(event['extendedProps']['home_address'], 'Av. de la Constitución 12')

if __name__ == '__main__':
    unittest.main()
