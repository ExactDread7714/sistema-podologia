import os
from datetime import datetime, date, time
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Appointment, ClinicalRecord, RecordPhoto

app = Flask(__name__)
app.config['SECRET_KEY'] = 'podologia_web_secret_key_1234'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///podologia.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de subida de imágenes
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB max

# Crear la carpeta de uploads si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Inicializar Base de Datos y Flask-Login
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor inicia sesión para acceder a esta página."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Inicialización de la DB y creación del podólogo por defecto
with app.app_context():
    db.create_all()
    # Verificar si ya existe un podólogo
    podologist = User.query.filter_by(role='podologist').first()
    if not podologist:
        admin = User(
            email='podologo@web.com',
            full_name='Dr. Carlos Martínez',
            phone='123456789',
            role='podologist',
            custom_price=0.0
        )
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()
        print("Podólogo por defecto creado: podologo@web.com / admin")

    # Verificar si ya existe un paciente de prueba
    patient = User.query.filter_by(role='patient').first()
    if not patient:
        test_patient = User(
            email='paciente@web.com',
            full_name='Juan Pérez',
            phone='987654321',
            role='patient',
            custom_price=35.0
        )
        test_patient.set_password('user')
        db.session.add(test_patient)
        db.session.commit()
        print("Paciente por defecto creado: paciente@web.com / user")


# Helper para verificar si el usuario es podólogo
def podologist_required(func):
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'podologist':
            flash("Acceso restringido. Solo para podólogos.", "danger")
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


# --- RUTAS DE AUTENTICACIÓN ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'podologist':
            return redirect(url_for('calendar_podologist'))
        else:
            return redirect(url_for('portal_paciente'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f"¡Bienvenido, {user.full_name}!", "success")
            if user.role == 'podologist':
                return redirect(url_for('calendar_podologist'))
            else:
                return redirect(url_for('portal_paciente'))
        else:
            flash("Correo electrónico o contraseña incorrectos.", "danger")

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        if current_user.role == 'podologist':
            return redirect(url_for('calendar_podologist'))
        else:
            return redirect(url_for('portal_paciente'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')

        if User.query.filter_by(email=email).first():
            flash("El correo electrónico ya está registrado.", "danger")
            return redirect(url_for('register'))

        new_user = User(
            email=email,
            full_name=full_name,
            phone=phone,
            role='patient',
            custom_price=0.0
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash("Registro completado con éxito. Ahora puedes iniciar sesión.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


# --- RUTAS DEL PODÓLOGO ---

@app.route('/')
@app.route('/calendar')
@login_required
@podologist_required
def calendar_podologist():
    # Obtener lista de pacientes para el modal de agendamiento rápido manual
    patients = User.query.filter_by(role='patient').all()
    return render_template('calendar_podologist.html', patients=patients)


@app.route('/api/appointments', methods=['GET', 'POST'])
@login_required
@podologist_required
def api_appointments():
    # El podólogo actual
    podo_id = current_user.id

    if request.method == 'GET':
        start_str = request.args.get('start')
        end_str = request.args.get('end')

        query = Appointment.query.filter_by(podologist_id=podo_id)

        if start_str and end_str:
            # FullCalendar envía fechas en formato ISO (e.g., 2023-10-01T00:00:00Z o similar)
            # Solo tomamos la parte de la fecha YYYY-MM-DD
            start_date = datetime.fromisoformat(start_str.split('T')[0]).date()
            end_date = datetime.fromisoformat(end_str.split('T')[0]).date()
            query = query.filter(Appointment.date >= start_date, Appointment.date <= end_date)

        appointments = query.all()
        events = []
        for appt in appointments:
            # Combinamos la fecha y la hora para formar ISO strings
            start_dt = datetime.combine(appt.date, appt.time).isoformat()
            # Asumimos que cada cita dura 30 minutos por defecto para FullCalendar
            end_time = datetime.combine(appt.date, appt.time)
            # sumamos 30 minutos de forma simple para la visualización del calendario
            from datetime import timedelta
            end_dt = (end_time + timedelta(minutes=30)).isoformat()

            # El título del evento será el nombre del paciente y el motivo
            patient_name = appt.patient.full_name if appt.patient else "Paciente Desconocido"

            # Definir color según el estado
            color = '#ffc107' # amarillo para pendiente
            if appt.status == 'approved':
                color = '#198754' # verde para aprobado
            elif appt.status == 'rejected':
                color = '#dc3545' # rojo para rechazado

            events.append({
                'id': appt.id,
                'title': f"{patient_name} - {appt.reason}",
                'start': start_dt,
                'end': end_dt,
                'backgroundColor': color,
                'borderColor': color,
                'textColor': '#ffffff',
                'extendedProps': {
                    'patient_id': appt.patient_id,
                    'patient_name': patient_name,
                    'reason': appt.reason,
                    'status': appt.status,
                    'time': appt.time.strftime('%H:%M'),
                    'date': appt.date.strftime('%Y-%m-%d'),
                    'custom_price': appt.patient.custom_price if appt.patient else 0.0
                }
            })
        return jsonify(events)

    elif request.method == 'POST':
        # Agendar cita manualmente
        data = request.json or request.form
        patient_id = data.get('patient_id')
        date_str = data.get('date')
        time_str = data.get('time')
        reason = data.get('reason')
        status = data.get('status', 'approved') # Por defecto aprobado si lo agenda el podólogo manualmente

        if not patient_id or not date_str or not time_str or not reason:
            return jsonify({'success': False, 'message': 'Faltan campos obligatorios.'}), 400

        try:
            appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            appt_time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return jsonify({'success': False, 'message': 'Formato de fecha u hora inválido.'}), 400

        new_appt = Appointment(
            patient_id=patient_id,
            podologist_id=podo_id,
            date=appt_date,
            time=appt_time,
            reason=reason,
            status=status
        )
        db.session.add(new_appt)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Cita agendada correctamente.', 'appointment_id': new_appt.id})


@app.route('/api/appointments/<int:appt_id>', methods=['PUT', 'DELETE'])
@login_required
@podologist_required
def api_modify_appointment(appt_id):
    appt = Appointment.query.filter_by(id=appt_id, podologist_id=current_user.id).first_or_404()

    if request.method == 'PUT':
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No se enviaron datos.'}), 400

        # Reprogramación por arrastrar/soltar o edición
        if 'date' in data:
            try:
                appt.date = datetime.strptime(data['date'].split('T')[0], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'success': False, 'message': 'Formato de fecha inválido.'}), 400

        if 'time' in data:
            try:
                # El formato de la hora puede ser HH:MM:SS o HH:MM
                t_str = data['time']
                if len(t_str) > 5:
                    t_str = t_str[:5]
                appt.time = datetime.strptime(t_str, '%H:%M').time()
            except ValueError:
                return jsonify({'success': False, 'message': 'Formato de hora inválido.'}), 400

        if 'status' in data:
            if data['status'] in ['pending', 'approved', 'rejected']:
                appt.status = data['status']

        if 'reason' in data:
            appt.reason = data['reason']

        db.session.commit()
        return jsonify({'success': True, 'message': 'Cita modificada correctamente.'})

    elif request.method == 'DELETE':
        db.session.delete(appt)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Cita eliminada correctamente.'})


@app.route('/patients', methods=['GET', 'POST'])
@login_required
@podologist_required
def patients_list():
    # Obtener todos los pacientes
    search_query = request.args.get('search', '').strip()
    if search_query:
        patients = User.query.filter(
            User.role == 'patient',
            (User.full_name.ilike(f'%{search_query}%')) |
            (User.email.ilike(f'%{search_query}%')) |
            (User.phone.ilike(f'%{search_query}%'))
        ).all()
    else:
        patients = User.query.filter_by(role='patient').all()

    if request.method == 'POST':
        # Registrar nuevo paciente manualmente
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        custom_price_str = request.form.get('custom_price', '0.0')

        try:
            custom_price = float(custom_price_str)
        except ValueError:
            custom_price = 0.0

        if not email or not full_name:
            flash("El nombre y correo electrónico son obligatorios.", "danger")
            return redirect(url_for('patients_list'))

        if User.query.filter_by(email=email).first():
            flash("El correo electrónico ya está registrado.", "danger")
            return redirect(url_for('patients_list'))

        # Crear cuenta del paciente con una contraseña temporal o su propio correo como contraseña por defecto
        new_patient = User(
            email=email,
            full_name=full_name,
            phone=phone,
            role='patient',
            custom_price=custom_price
        )
        # La contraseña por defecto para el paciente registrado manualmente será su propio teléfono o 'paciente123'
        new_patient.set_password(phone if phone else 'paciente123')
        db.session.add(new_patient)
        db.session.commit()

        flash(f"Paciente {full_name} registrado correctamente.", "success")
        return redirect(url_for('patients_list'))

    return render_template('patients_list.html', patients=patients, search_query=search_query)


@app.route('/patients/<int:patient_id>', methods=['GET'])
@login_required
@podologist_required
def patient_profile(patient_id):
    patient = User.query.filter_by(id=patient_id, role='patient').first_or_404()
    # Historial de registros clínicos de este paciente, ordenados por fecha descendente
    records = ClinicalRecord.query.filter_by(patient_id=patient_id).order_by(ClinicalRecord.date.desc()).all()
    return render_template('patient_profile.html', patient=patient, records=records)


@app.route('/patients/<int:patient_id>/edit', methods=['POST'])
@login_required
@podologist_required
def edit_patient_profile(patient_id):
    patient = User.query.filter_by(id=patient_id, role='patient').first_or_404()

    email = request.form.get('email')
    full_name = request.form.get('full_name')
    phone = request.form.get('phone')
    custom_price_str = request.form.get('custom_price', '0.0')

    try:
        custom_price = float(custom_price_str)
    except ValueError:
        custom_price = 0.0

    if not email or not full_name:
        flash("El nombre y el correo electrónico son obligatorios.", "danger")
        return redirect(url_for('patient_profile', patient_id=patient.id))

    # Verificar si el email ya existe en otro usuario
    existing_user = User.query.filter(User.email == email, User.id != patient.id).first()
    if existing_user:
        flash("El correo electrónico ya está registrado por otro usuario.", "danger")
        return redirect(url_for('patient_profile', patient_id=patient.id))

    patient.email = email
    patient.full_name = full_name
    patient.phone = phone
    patient.custom_price = custom_price

    db.session.commit()
    flash("Perfil del paciente actualizado correctamente.", "success")
    return redirect(url_for('patient_profile', patient_id=patient.id))


# --- CONSULTA ACTIVA (ATENCION) ---

@app.route('/atencion/<int:appointment_id>', methods=['GET'])
@login_required
@podologist_required
def atencion(appointment_id):
    appt = Appointment.query.filter_by(id=appointment_id, podologist_id=current_user.id).first_or_404()
    patient = appt.patient
    return render_template('atencion.html', appointment=appt, patient=patient)


@app.route('/atencion/<int:appointment_id>/save', methods=['POST'])
@login_required
@podologist_required
def save_atencion(appointment_id):
    appt = Appointment.query.filter_by(id=appointment_id, podologist_id=current_user.id).first_or_404()

    diagnosis_treatment = request.form.get('diagnosis_treatment')
    patient_instructions = request.form.get('patient_instructions')

    if not diagnosis_treatment or not patient_instructions:
        flash("Ambos campos son obligatorios para guardar la consulta.", "danger")
        return redirect(url_for('atencion', appointment_id=appt.id))

    # Crear el registro clínico
    new_record = ClinicalRecord(
        appointment_id=appt.id,
        patient_id=appt.patient_id,
        podologist_id=current_user.id,
        date=datetime.now().date(),
        diagnosis_treatment=diagnosis_treatment,
        patient_instructions=patient_instructions
    )
    db.session.add(new_record)
    db.session.flush() # Para obtener el ID del registro clínico recién creado antes del commit

    # Marcar la cita como aprobada/atendida
    appt.status = 'approved'

    # Procesar la subida de fotos (pueden ser múltiples archivos si se desea, o uno solo)
    files = request.files.getlist('photos')
    for file in files:
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            # Agregar un timestamp para que el nombre de archivo sea único
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)

            # Crear el registro de la foto
            photo_url = url_for('static', filename=f"uploads/{unique_filename}")
            new_photo = RecordPhoto(
                clinical_record_id=new_record.id,
                photo_url=photo_url
            )
            db.session.add(new_photo)

    db.session.commit()
    flash("Consulta clínica guardada correctamente.", "success")
    return redirect(url_for('patient_profile', patient_id=appt.patient_id))


# --- RUTAS DE PACIENTES (PÚBLICAS O PACIENTE LOGUEADO) ---

@app.route('/reservar', methods=['GET', 'POST'])
def reservar():
    # Si el usuario está autenticado y es podólogo, redirigir
    if current_user.is_authenticated and current_user.role == 'podologist':
        return redirect(url_for('calendar_podologist'))

    # Buscar el primer podólogo de la base de datos para asignar la cita
    podo = User.query.filter_by(role='podologist').first()
    if not podo:
        flash("Lo sentimos, no hay ningún podólogo disponible en este momento.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        reason = request.form.get('reason')

        if not date_str or not time_str or not reason:
            flash("Todos los campos son obligatorios.", "danger")
            return redirect(url_for('reservar'))

        try:
            appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            appt_time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            flash("Formato de fecha u hora no válido.", "danger")
            return redirect(url_for('reservar'))

        # Si el usuario ya está autenticado como paciente
        if current_user.is_authenticated and current_user.role == 'patient':
            patient_id = current_user.id
        else:
            # Caso de solicitud pública por paciente no logueado
            email = request.form.get('email')
            full_name = request.form.get('full_name')
            phone = request.form.get('phone')

            if not email or not full_name:
                flash("Debes ingresar tu nombre y correo electrónico para solicitar una cita.", "danger")
                return redirect(url_for('reservar'))

            # Buscar si el paciente ya tiene cuenta
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                patient_id = existing_user.id
            else:
                # Crear nueva cuenta de paciente de forma automática
                new_patient = User(
                    email=email,
                    full_name=full_name,
                    phone=phone,
                    role='patient',
                    custom_price=0.0
                )
                new_patient.set_password(phone if phone else 'paciente123')
                db.session.add(new_patient)
                db.session.flush() # Obtener el ID
                patient_id = new_patient.id

        # Crear la cita en estado "pending" (pendiente)
        new_appt = Appointment(
            patient_id=patient_id,
            podologist_id=podo.id,
            date=appt_date,
            time=appt_time,
            reason=reason,
            status='pending'
        )
        db.session.add(new_appt)
        db.session.commit()

        if current_user.is_authenticated:
            flash("¡Cita solicitada con éxito! Esperando aprobación del podólogo.", "success")
            return redirect(url_for('portal_paciente'))
        else:
            flash("¡Cita solicitada con éxito! Te hemos registrado una cuenta automática con tu correo. Puedes iniciar sesión usando tu teléfono o 'paciente123' como contraseña.", "success")
            return redirect(url_for('login'))

    return render_template('reservar.html', today=date.today())


@app.route('/portal')
@login_required
def portal_paciente():
    if current_user.role != 'patient':
        return redirect(url_for('calendar_podologist'))

    # Citas del paciente
    appointments = Appointment.query.filter_by(patient_id=current_user.id).order_by(Appointment.date.desc(), Appointment.time.desc()).all()

    # Resúmenes clínicos del paciente (únicamente mostramos `patient_instructions`)
    records = ClinicalRecord.query.filter_by(patient_id=current_user.id).order_by(ClinicalRecord.date.desc()).all()

    return render_template('portal_paciente.html', appointments=appointments, records=records)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
