from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

APPEAL_CATEGORIES = {
    'complaint': 'Жалоба на действия сотрудников',
    'crime': 'Заявление о преступлении',
    'traffic': 'Дорожное происшествие',
    'other': 'Другое',
}

APPEAL_STATUSES = {
    'received': 'Принято',
    'in_progress': 'В рассмотрении',
    'closed': 'Обращение закрыто',
    'rejected': 'Отклонено',
}

RATING_OPTIONS = {
    'satisfied': 'Удовлетворён',
    'partial': 'Частично удовлетворён',
    'unsatisfied': 'Не удовлетворён',
}


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    last_name = db.Column(db.String(80), nullable=False, default='')
    first_name = db.Column(db.String(80), nullable=False, default='')
    patronymic = db.Column(db.String(80))
    full_name = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(300))
    email_verified = db.Column(db.Boolean, default=True, nullable=False)
    email_verify_code = db.Column(db.String(6))
    email_verify_expires = db.Column(db.DateTime)
    reset_token = db.Column(db.String(128))
    reset_token_expires = db.Column(db.DateTime)
    role = db.Column(db.String(20), nullable=False, default='citizen')
    appeals = db.relationship('Appeal', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def fio(self):
        parts = [self.last_name, self.first_name, self.patronymic or '']
        return ' '.join(p for p in parts if p).strip() or (self.full_name or '')

    def sync_full_name(self):
        self.full_name = self.fio

    @property
    def is_staff(self):
        return self.role == 'staff'


class Appeal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_number = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_anonymous = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(50), nullable=False, default='other')
    status = db.Column(db.String(50), nullable=False, default='received')
    last_name = db.Column(db.String(80))
    first_name = db.Column(db.String(80))
    patronymic = db.Column(db.String(80))
    full_name = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.String(300))
    appeal_text = db.Column(db.Text, nullable=False)
    photo_path = db.Column(db.String(300))
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)
    files = db.relationship('AppealFile', backref='appeal', lazy=True, cascade='all, delete-orphan')
    status_history = db.relationship('AppealStatusHistory', backref='appeal', lazy=True, cascade='all, delete-orphan')
    rating = db.relationship('AppealRating', backref='appeal', uselist=False, cascade='all, delete-orphan')

    @staticmethod
    def generate_registration_number(appeal_id):
        year = datetime.utcnow().year
        return f'ОБР-{year}-{appeal_id:05d}'

    @property
    def category_label(self):
        return APPEAL_CATEGORIES.get(self.category, self.category)

    @property
    def status_label(self):
        return APPEAL_STATUSES.get(self.status, self.status)

    @property
    def applicant_fio(self):
        if self.last_name or self.first_name:
            return ' '.join(filter(None, [self.last_name, self.first_name, self.patronymic]))
        return self.full_name or '—'


class AppealFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appeal_id = db.Column(db.Integer, db.ForeignKey('appeal.id'), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class AppealStatusHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appeal_id = db.Column(db.Integer, db.ForeignKey('appeal.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    comment = db.Column(db.Text)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def status_label(self):
        return APPEAL_STATUSES.get(self.status, self.status)


class AppealRating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appeal_id = db.Column(db.Integer, db.ForeignKey('appeal.id'), nullable=False, unique=True)
    rating = db.Column(db.String(20), nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def rating_label(self):
        return RATING_OPTIONS.get(self.rating, self.rating)
