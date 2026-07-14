import unittest
from app import app, db, User

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

if __name__ == '__main__':
    unittest.main()
