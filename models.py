from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(300))
    email = db.Column(db.String(120))

class Appeal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_anonymous = db.Column(db.Boolean, default=False)
    full_name = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.String(300))
    appeal_text = db.Column(db.Text, nullable=False)
    photo_path = db.Column(db.String(300))
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)