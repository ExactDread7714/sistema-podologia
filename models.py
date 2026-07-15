from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    role = db.Column(db.String(20), default='patient', nullable=False) # 'podologist' o 'patient'
    custom_price = db.Column(db.Float, default=0.0, nullable=False) # Solo visible/editable por el podólogo

    # Relaciones
    # Citas donde el usuario es paciente
    appointments_as_patient = db.relationship('Appointment', foreign_keys='Appointment.patient_id', backref='patient', lazy=True, cascade="all, delete-orphan")
    # Citas donde el usuario es el podólogo
    appointments_as_podologist = db.relationship('Appointment', foreign_keys='Appointment.podologist_id', backref='podologist', lazy=True)

    # Registros clínicos como paciente
    clinical_records_as_patient = db.relationship('ClinicalRecord', foreign_keys='ClinicalRecord.patient_id', backref='patient', lazy=True, cascade="all, delete-orphan")
    # Registros clínicos como podólogo
    clinical_records_as_podologist = db.relationship('ClinicalRecord', foreign_keys='ClinicalRecord.podologist_id', backref='podologist', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Appointment(db.Model):
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    podologist_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False) # YYYY-MM-DD
    time = db.Column(db.Time, nullable=False) # HH:MM:SS
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False) # 'pending', 'approved', 'rejected'

    # NUEVOS CAMPOS: Visitas a domicilio y Duración
    is_home_visit = db.Column(db.Boolean, default=False, nullable=False)
    home_address = db.Column(db.String(255), nullable=True)
    duration_minutes = db.Column(db.Integer, default=30, nullable=False) # Definido por el podólogo para bloquear horas en su calendario

    # Relación uno-a-uno o uno-a-muchos con ClinicalRecord
    clinical_records = db.relationship('ClinicalRecord', backref='appointment', lazy=True, cascade="all, delete-orphan")


class ClinicalRecord(db.Model):
    __tablename__ = 'clinical_records'

    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id', ondelete="CASCADE"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    podologist_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    diagnosis_treatment = db.Column(db.Text, nullable=False)
    patient_instructions = db.Column(db.Text, nullable=False)

    # Relación con fotos
    photos = db.relationship('RecordPhoto', backref='clinical_record', lazy=True, cascade="all, delete-orphan")


class RecordPhoto(db.Model):
    __tablename__ = 'record_photos'

    id = db.Column(db.Integer, primary_key=True)
    clinical_record_id = db.Column(db.Integer, db.ForeignKey('clinical_records.id', ondelete="CASCADE"), nullable=False)
    photo_url = db.Column(db.String(255), nullable=False)
