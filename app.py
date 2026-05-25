import json
import os
import random
import re
import secrets
import smtplib
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import uuid4

from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from markupsafe import escape
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from functools import wraps
from sqlalchemy import inspect, or_, text
from werkzeug.utils import secure_filename

from config import Config
from models import (
    APPEAL_CATEGORIES,
    APPEAL_STATUSES,
    RATING_OPTIONS,
    Appeal,
    AppealFile,
    AppealRating,
    AppealStatusHistory,
    User,
    db,
)

app = Flask(__name__)
app.config.from_object(Config)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)

if os.getenv('BEHIND_PROXY', '0') == '1':
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Для доступа войдите в личный кабинет.'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(__file__), 'instance'), exist_ok=True)

RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL', 'oktyabrsky28@gmail.com').strip().lower()
STAFF_EMAILS = {'oktyabrsky28@gmail.com'}
STAFF_SKIP_EMAIL_VERIFY = os.getenv('STAFF_SKIP_EMAIL_VERIFY', '0') == '1'
PER_PAGE = 10


def get_staff_access_code():
    return os.getenv('STAFF_ACCESS_CODE', '').strip()


def verify_staff_access_code(code):
    expected = get_staff_access_code()
    if not expected:
        return False
    return (code or '').strip() == expected
MAX_APPEAL_TEXT = 5000
SORT_COLUMNS = {
    'registration_number': Appeal.registration_number,
    'date_submitted': Appeal.date_submitted,
    'status': Appeal.status,
    'category': Appeal.category,
}


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def staff_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_staff:
            flash('Доступ только для сотрудников МО МВД.', 'danger')
            return redirect(url_for('cabinet'))
        return view(*args, **kwargs)
    return wrapped


def home_url_for_user(user):
    return url_for('staff_panel') if user.is_staff else url_for('cabinet')


def can_access_appeal(appeal, user):
    if user.is_staff:
        return True
    return appeal.user_id == user.id or appeal.email == user.email or appeal.phone == user.phone


def is_valid_email(email):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', (email or '').strip()))


def validate_password(password):
    if len(password) < 8:
        return 'Пароль должен содержать минимум 8 символов.'
    if not re.search(r'[A-ZА-Я]', password):
        return 'Пароль должен содержать заглавную букву.'
    if not re.search(r'[a-zа-я]', password):
        return 'Пароль должен содержать строчную букву.'
    if not re.search(r'\d', password):
        return 'Пароль должен содержать цифру.'
    return None


def normalize_phone(phone):
    digits = re.sub(r'\D', '', phone or '')
    if not digits:
        return ''
    if digits.startswith('8'):
        digits = '7' + digits[1:]
    elif not digits.startswith('7'):
        digits = '7' + digits
    return f'+{digits}'


_LAST_EMAIL_ERROR = ''


def is_render_free_smtp_blocked():
    if os.getenv('RENDER', '').lower() not in ('true', '1', 'yes'):
        return False
    instance = os.getenv('RENDER_INSTANCE_TYPE', 'free').lower()
    return instance in ('', 'free')


def email_configured():
    if os.getenv('RESEND_API_KEY', '').strip():
        return True
    return bool(os.getenv('EMAIL_USER', '').strip() and os.getenv('EMAIL_PASS', '').strip())


def get_last_email_error():
    return _LAST_EMAIL_ERROR


def send_via_resend(to_email, subject, body):
    global _LAST_EMAIL_ERROR
    api_key = os.getenv('RESEND_API_KEY', '').strip()
    from_addr = (
        os.getenv('RESEND_FROM', '').strip()
        or os.getenv('EMAIL_USER', '').strip()
        or 'onboarding@resend.dev'
    )
    payload = json.dumps(
        {'from': from_addr, 'to': [to_email], 'subject': subject, 'text': body},
        ensure_ascii=False,
    ).encode('utf-8')
    req = Request(
        'https://api.resend.com/emails',
        data=payload,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(req, timeout=25) as resp:
            if 200 <= resp.status < 300:
                return True
            _LAST_EMAIL_ERROR = f'Resend HTTP {resp.status}'
            return False
    except HTTPError as e:
        detail = e.read().decode('utf-8', errors='replace')[:400]
        _LAST_EMAIL_ERROR = f'Resend {e.code}: {detail}'
        print('Ошибка Resend:', _LAST_EMAIL_ERROR)
        return False
    except (URLError, TimeoutError, OSError) as e:
        _LAST_EMAIL_ERROR = f'Resend: {e}'
        print('Ошибка Resend:', e)
        return False


def send_via_smtp(to_email, subject, body):
    global _LAST_EMAIL_ERROR
    email_user = os.getenv('EMAIL_USER', '').strip()
    email_pass = os.getenv('EMAIL_PASS', '').strip()
    if not email_user or not email_pass:
        _LAST_EMAIL_ERROR = 'Не заданы EMAIL_USER или EMAIL_PASS'
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        smtp_host = os.getenv('SMTP_SERVER', 'smtp.gmail.com').strip()
        server = smtplib.SMTP(smtp_host, 587, timeout=15)
        server.starttls()
        server.login(email_user, email_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        err = str(e).lower()
        print('Ошибка SMTP:', e)
        if is_render_free_smtp_blocked() and ('timed out' in err or 'timeout' in err or '10060' in err):
            _LAST_EMAIL_ERROR = (
                'Бесплатный Render блокирует Gmail SMTP. Добавьте RESEND_API_KEY или используйте admin/setup-staff.'
            )
        else:
            _LAST_EMAIL_ERROR = str(e)
        return False


def send_email(to_email, subject, body):
    global _LAST_EMAIL_ERROR
    _LAST_EMAIL_ERROR = ''
    if os.getenv('RESEND_API_KEY', '').strip():
        return send_via_resend(to_email, subject, body)
    if not os.getenv('EMAIL_USER', '').strip() or not os.getenv('EMAIL_PASS', '').strip():
        _LAST_EMAIL_ERROR = 'Не заданы EMAIL_USER или EMAIL_PASS'
        print('Ошибка почты:', _LAST_EMAIL_ERROR)
        return False
    return send_via_smtp(to_email, subject, body)


def mask_email(email):
    if not email or '@' not in email:
        return email or ''
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        masked_local = local[0] + '***'
    else:
        masked_local = local[0] + '***' + local[-1]
    return f'{masked_local}@{domain}'


def generate_email_verify_code():
    return f'{random.randint(0, 999999):06d}'


def issue_email_verify_code(user):
    """Сохраняет код в БД и отправляет письмо. Возвращает (успех_отправки, код)."""
    user.email_verify_code = generate_email_verify_code()
    user.email_verify_expires = datetime.utcnow() + timedelta(minutes=15)
    user.email_verified = False
    code = user.email_verify_code
    body = (
        f'Код подтверждения регистрации: {code}\n\n'
        'Введите его на странице подтверждения email.\n'
        'Код действует 15 минут.'
    )
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print('Ошибка сохранения кода:', e)
        return False, None
    if send_email(user.email, 'Код подтверждения — МО МВД Октябрьский', body):
        return True, code
    print('Письмо с кодом не отправлено на', user.email)
    return False, code


def optional_phone(phone):
    return normalize_phone(phone) or ''


def find_user_by_login(login_value):
    login_value = (login_value or '').strip()
    if not login_value:
        return None
    if '@' in login_value:
        return User.query.filter_by(email=login_value.lower()).first()
    phone = normalize_phone(login_value)
    if phone:
        user = User.query.filter_by(phone=phone).first()
        if user:
            return user
    return User.query.filter_by(email=login_value.lower()).first()


def clear_all_data():
    users = User.query.count()
    appeals = Appeal.query.count()
    AppealRating.query.delete()
    AppealStatusHistory.query.delete()
    AppealFile.query.delete()
    Appeal.query.delete()
    User.query.delete()
    db.session.commit()
    return users, appeals


def migrate_db():
    inspector = inspect(db.engine)
    if 'user' not in inspector.get_table_names():
        db.create_all()
        return

    user_cols = {c['name'] for c in inspector.get_columns('user')}
    user_migrations = {
        'last_name': "VARCHAR(80) DEFAULT ''",
        'first_name': "VARCHAR(80) DEFAULT ''",
        'patronymic': 'VARCHAR(80)',
        'reset_token': 'VARCHAR(128)',
        'reset_token_expires': 'DATETIME',
        'role': "VARCHAR(20) DEFAULT 'citizen'",
        'email_verify_code': 'VARCHAR(6)',
        'email_verify_expires': 'DATETIME',
        'email_verified': 'BOOLEAN DEFAULT 1',
    }
    for name, col_type in user_migrations.items():
        if name not in user_cols:
            db.session.execute(text(f'ALTER TABLE user ADD COLUMN {name} {col_type}'))

    appeal_cols = {c['name'] for c in inspector.get_columns('appeal')} if 'appeal' in inspector.get_table_names() else set()
    appeal_migrations = {
        'last_name': 'VARCHAR(80)',
        'first_name': 'VARCHAR(80)',
        'patronymic': 'VARCHAR(80)',
    }
    for name, col_type in appeal_migrations.items():
        if name not in appeal_cols:
            db.session.execute(text(f'ALTER TABLE appeal ADD COLUMN {name} {col_type}'))

    db.session.execute(text("UPDATE user SET email = 'user' || id || '@legacy.local' WHERE email IS NULL OR TRIM(email) = ''"))
    db.session.execute(text("UPDATE user SET last_name = COALESCE(NULLIF(full_name, ''), 'Пользователь') WHERE last_name IS NULL OR last_name = ''"))
    db.session.execute(text("UPDATE user SET first_name = '' WHERE first_name IS NULL"))
    db.session.execute(text("UPDATE user SET email_verified = 1 WHERE role IS NULL OR role = '' OR role = 'citizen'"))
    db.session.execute(text("UPDATE user SET role = 'citizen' WHERE role IS NULL OR TRIM(role) = ''"))
    db.session.execute(text("UPDATE user SET role = 'staff' WHERE LOWER(email) = 'oktyabrsky28@gmail.com'"))
    db.session.execute(text("UPDATE appeal SET status = 'closed' WHERE status = 'completed'"))
    db.session.commit()
    db.create_all()


def add_status_history(appeal, status, comment=''):
    entry = AppealStatusHistory(appeal_id=appeal.id, status=status, comment=comment)
    db.session.add(entry)


def save_appeal_files(appeal, file_list):
    saved = []
    for file in file_list:
        if not file or not file.filename:
            continue
        original = secure_filename(file.filename)
        if not original:
            continue
        stored = f'{uuid4().hex}_{original}'
        path = os.path.join(app.config['UPLOAD_FOLDER'], stored)
        file.save(path)
        db.session.add(AppealFile(appeal_id=appeal.id, original_name=original, stored_name=stored))
        saved.append(stored)
    return saved


def create_appeal_from_form(form, files, user=None):
    appeal = Appeal(
        registration_number='TEMP',
        user_id=user.id if user else None,
        is_anonymous=not user,
        category=form.get('category', 'other'),
        status='received',
        last_name=form.get('last_name', '').strip() or None,
        first_name=form.get('first_name', '').strip() or None,
        patronymic=form.get('patronymic', '').strip() or None,
        full_name=' '.join(filter(None, [
            form.get('last_name', '').strip(),
            form.get('first_name', '').strip(),
            form.get('patronymic', '').strip(),
        ])) or None,
        email=(form.get('email') or (user.email if user else '')).strip().lower(),
        phone=normalize_phone(form.get('phone', '')) or (user.phone if user else None),
        address=form.get('address', '').strip() or (user.address if user else None),
        appeal_text=form.get('appeal_text', '').strip(),
    )
    db.session.add(appeal)
    db.session.flush()
    appeal.registration_number = Appeal.generate_registration_number(appeal.id)
    add_status_history(appeal, 'received', 'Обращение зарегистрировано в системе')
    save_appeal_files(appeal, files)
    db.session.commit()
    return appeal


def user_appeals_query(user):
    return Appeal.query.filter(
        or_(Appeal.user_id == user.id, Appeal.email == user.email, Appeal.phone == user.phone),
        Appeal.is_anonymous == False,
    )


def build_cabinet_url(**kwargs):
    return url_for('cabinet', **{k: v for k, v in kwargs.items() if v})


def build_staff_url(**kwargs):
    return url_for('staff_panel', **{k: v for k, v in kwargs.items() if v})


def apply_appeal_filters(query, category, status, date_from, date_to):
    if category in APPEAL_CATEGORIES:
        query = query.filter(Appeal.category == category)
    if status in APPEAL_STATUSES:
        query = query.filter(Appeal.status == status)
    if date_from:
        try:
            query = query.filter(Appeal.date_submitted >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(Appeal.date_submitted <= dt)
        except ValueError:
            pass
    return query


def send_appeal_notification(appeal):
    body = f"""Новое обращение {appeal.registration_number}
Категория: {appeal.category_label}
ФИО: {appeal.applicant_fio}
Email: {appeal.email or '—'}
Телефон: {appeal.phone or '—'}

{appeal.appeal_text}
"""
    return send_email(RECIPIENT_EMAIL, f'Обращение {appeal.registration_number}', body)


NEWS_FILE = os.path.join(os.path.dirname(__file__), 'static', 'data', 'news.json')


def load_news_items():
    try:
        with open(NEWS_FILE, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError) as e:
        print('Ошибка загрузки новостей:', e)
        return []


@app.route('/api/news')
def api_news():
    return jsonify(load_news_items())


@app.route('/')
def index():
    return render_template('home.html', news_items=load_news_items())


@app.route('/appeal/submit', methods=['GET', 'POST'])
def submit_appeal():
    if request.method == 'POST':
        if not request.form.get('consent'):
            flash('Необходимо согласие на обработку персональных данных.', 'danger')
            return redirect(url_for('submit_appeal'))

        appeal_text = request.form.get('appeal_text', '').strip()
        if not appeal_text:
            flash('Укажите текст обращения.', 'danger')
            return redirect(url_for('submit_appeal'))
        if len(appeal_text) > MAX_APPEAL_TEXT:
            flash(f'Текст обращения не должен превышать {MAX_APPEAL_TEXT} символов.', 'danger')
            return redirect(url_for('submit_appeal'))

        email = request.form.get('email', '').strip().lower()
        if not current_user.is_authenticated:
            if email and not is_valid_email(email):
                flash('Укажите корректный email для уведомлений.', 'danger')
                return redirect(url_for('submit_appeal'))

        form_data = dict(request.form)
        if current_user.is_authenticated:
            form_data['last_name'] = current_user.last_name
            form_data['first_name'] = current_user.first_name
            form_data['patronymic'] = current_user.patronymic or ''
            form_data['email'] = current_user.email

        appeal = create_appeal_from_form(form_data, request.files.getlist('files'), current_user if current_user.is_authenticated else None)
        send_appeal_notification(appeal)
        flash(f'Обращение {appeal.registration_number} успешно отправлено.', 'success')
        return redirect(url_for('check_status', number=appeal.registration_number, email=appeal.email or ''))

    profile = current_user if current_user.is_authenticated else None
    return render_template('submit_appeal.html', categories=APPEAL_CATEGORIES, profile=profile, max_text=MAX_APPEAL_TEXT)


@app.route('/check-status', methods=['GET', 'POST'])
def check_status():
    appeal = None
    history = []
    reg_number = request.args.get('number', '') or request.form.get('registration_number', '')
    email = request.args.get('email', '') or request.form.get('email', '')

    if request.method == 'POST' or (reg_number and email):
        reg_number = reg_number.strip()
        email = email.strip().lower()
        appeal = Appeal.query.filter_by(registration_number=reg_number).first()
        if appeal and appeal.email and appeal.email.lower() == email:
            history = AppealStatusHistory.query.filter_by(appeal_id=appeal.id).order_by(AppealStatusHistory.changed_at.asc()).all()
        elif request.method == 'POST':
            flash('Обращение не найдено или email не совпадает.', 'danger')
            appeal = None

    return render_template('check_status.html', appeal=appeal, history=history, reg_number=reg_number, email=email)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(home_url_for_user(current_user))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        last_name = request.form.get('last_name', '').strip()
        first_name = request.form.get('first_name', '').strip()
        patronymic = request.form.get('patronymic', '').strip()
        role = request.form.get('role', 'citizen')
        is_staff = role == 'staff'

        if not all([email, password, password2, last_name, first_name]):
            flash('Заполните все обязательные поля.', 'danger')
            return redirect(url_for('register'))
        if not is_staff and not request.form.get('consent'):
            flash('Необходимо согласие на обработку персональных данных.', 'danger')
            return redirect(url_for('register'))
        if not is_valid_email(email):
            flash('Укажите корректный email.', 'danger')
            return redirect(url_for('register'))
        if is_staff and email not in STAFF_EMAILS:
            flash('Регистрация сотрудника доступна только для служебного email МО МВД.', 'danger')
            return redirect(url_for('register'))
        pwd_error = validate_password(password)
        if pwd_error:
            flash(pwd_error, 'danger')
            return redirect(url_for('register'))
        if password != password2:
            flash('Пароли не совпадают.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Этот email уже зарегистрирован. Войдите или восстановите пароль.', 'warning')
            return redirect(url_for('login'))

        user = User(
            email=email,
            last_name=last_name,
            first_name=first_name,
            patronymic=patronymic or None,
            phone=optional_phone(request.form.get('phone', '')) if not is_staff else '—',
            address=(request.form.get('address', '').strip() or None) if not is_staff else None,
            email_verified=False if is_staff else True,
            role='staff' if is_staff else 'citizen',
        )
        user.sync_full_name()
        user.set_password(password)
        db.session.add(user)

        try:
            if is_staff:
                staff_code = request.form.get('staff_code', '').strip()
                if not get_staff_access_code():
                    flash('Служебный код не настроен на сервере (STAFF_ACCESS_CODE).', 'danger')
                    return redirect(url_for('register'))
                if not verify_staff_access_code(staff_code):
                    flash('Неверный служебный код доступа сотрудника.', 'danger')
                    return redirect(url_for('register'))
                user.email_verified = True
                user.email_verify_code = None
                user.email_verify_expires = None
                db.session.commit()
                flash('Регистрация сотрудника успешна. Войдите в панель обработки обращений.', 'success')
                return redirect(url_for('login'))

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print('Ошибка регистрации:', e)
            flash('Ошибка при сохранении данных. Попробуйте ещё раз через минуту.', 'danger')
            return redirect(url_for('register'))

        flash('Регистрация успешна. Войдите в личный кабинет.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/register/verify', methods=['GET', 'POST'])
def register_verify():
    email = (request.args.get('email') or request.form.get('email', '')).strip().lower()
    user = User.query.filter_by(email=email, role='staff').first() if email else None

    if request.method == 'POST':
        action = request.form.get('action', 'verify')
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email, role='staff').first()
        if not user:
            flash('Аккаунт не найден. Зарегистрируйтесь как сотрудник.', 'danger')
            return redirect(url_for('register'))

        if action == 'resend':
            if not email_configured():
                flash(
                    'Почта не настроена. Добавьте EMAIL_USER/EMAIL_PASS или RESEND_API_KEY в .env / Render.',
                    'danger',
                )
                return redirect(url_for('register_verify', email=email))
            email_sent, verify_code = issue_email_verify_code(user)
            if email_sent:
                flash('Новый код отправлен на email. Проверьте папку «Спам».', 'info')
                return redirect(url_for('register_verify', email=email))
            flash('Письмо не отправилось. Используйте код на странице.', 'warning')
            return redirect(url_for('register_verify', email=email, show_code=1))

        code = request.form.get('code', '').strip()
        if not code:
            flash('Введите код из письма.', 'danger')
            return redirect(url_for('register_verify', email=email))
        if not user.email_verify_code or not user.email_verify_expires:
            flash('Код не был отправлен. Запросите новый.', 'danger')
            return redirect(url_for('register_verify', email=email))
        if user.email_verify_expires < datetime.utcnow():
            flash('Срок действия кода истёк. Запросите новый код.', 'danger')
            return redirect(url_for('register_verify', email=email))
        if code != user.email_verify_code:
            flash('Неверный код. Проверьте письмо и попробуйте снова.', 'danger')
            return redirect(url_for('register_verify', email=email))

        user.email_verified = True
        user.email_verify_code = None
        user.email_verify_expires = None
        db.session.commit()
        flash('Email подтверждён. Войдите в панель сотрудника.', 'success')
        return redirect(url_for('login'))

    if user and user.email_verified:
        flash('Email уже подтверждён. Войдите в систему.', 'info')
        return redirect(url_for('login'))

    show_code = request.args.get('show_code') == '1'
    verify_code = user.email_verify_code if (user and show_code) else None
    return render_template(
        'register_verify.html',
        email=email,
        masked_email=mask_email(email) if email else '',
        show_code=show_code,
        verify_code=verify_code,
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(home_url_for_user(current_user))
    if request.method == 'POST':
        login_value = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        staff_mode = request.form.get('login_mode') == 'staff'
        staff_code = request.form.get('staff_code', '').strip()

        if staff_mode:
            if not get_staff_access_code():
                flash('Служебный код не настроен на сервере (STAFF_ACCESS_CODE).', 'danger')
                return redirect(url_for('login'))
            if not verify_staff_access_code(staff_code):
                flash('Неверный служебный код доступа сотрудника.', 'danger')
                return redirect(url_for('login'))

        user = find_user_by_login(login_value)
        if not user:
            flash('Аккаунт с таким email или телефоном не найден.', 'danger')
        elif staff_mode and not user.is_staff:
            flash('Этот аккаунт не зарегистрирован как сотрудник МО МВД.', 'danger')
        elif not user.check_password(password):
            flash('Неверный пароль. Попробуйте снова или восстановите пароль.', 'danger')
        elif user.is_staff and not staff_mode:
            flash('Для входа сотрудника выберите «Я сотрудник» и введите служебный код.', 'warning')
        else:
            if user.is_staff and staff_mode and not user.email_verified:
                user.email_verified = True
                user.email_verify_code = None
                user.email_verify_expires = None
                db.session.commit()
            elif user.is_staff and not user.email_verified and not staff_mode:
                flash('Для входа сотрудника выберите «Я сотрудник» и введите служебный код.', 'warning')
                return redirect(url_for('login'))
            login_user(user, remember=remember)
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(home_url_for_user(user))
    return render_template('login.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            reset_url = url_for('reset_password', token=token, _external=True)
            if send_email(
                user.email,
                'Сброс пароля — МО МВД Октябрьский',
                f'Ссылка для сброса пароля:\n{reset_url}\n\nДействует 1 час.',
            ):
                flash('Ссылка для сброса пароля отправлена на email. Проверьте также папку «Спам».', 'success')
                return redirect(url_for('login'))
            return render_template(
                'forgot_password_link.html',
                reset_url=reset_url,
                email=mask_email(user.email),
            )
        flash('Если аккаунт существует, ссылка для сброса пароля отправлена на email.', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        flash('Ссылка недействительна или устарела.', 'danger')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        pwd_error = validate_password(password)
        if pwd_error:
            flash(pwd_error, 'danger')
            return redirect(url_for('reset_password', token=token))
        if password != password2:
            flash('Пароли не совпадают.', 'danger')
            return redirect(url_for('reset_password', token=token))
        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        flash('Пароль изменён. Войдите в систему.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html', email=user.email)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/cabinet')
@login_required
def cabinet():
    if current_user.is_staff:
        return redirect(url_for('staff_panel'))

    category = request.args.get('category', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    sort = request.args.get('sort', 'date_submitted')
    order = request.args.get('order', 'desc')
    page = request.args.get('page', 1, type=int)

    query = apply_appeal_filters(user_appeals_query(current_user), category, status, date_from, date_to)

    sort_column = SORT_COLUMNS.get(sort, Appeal.date_submitted)
    query = query.order_by(sort_column.asc() if order == 'asc' else sort_column.desc())
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    filters = {'category': category, 'status': status, 'date_from': date_from, 'date_to': date_to, 'sort': sort, 'order': order}

    def sort_url(column):
        new_order = 'asc' if sort == column and order == 'desc' else 'desc' if sort == column else 'asc'
        return build_cabinet_url(category=category, status=status, date_from=date_from, date_to=date_to, sort=column, order=new_order, page=1)

    def page_url(page_num):
        return build_cabinet_url(category=category, status=status, date_from=date_from, date_to=date_to, sort=sort, order=order, page=page_num)

    return render_template('cabinet.html', appeals=pagination.items, pagination=pagination, categories=APPEAL_CATEGORIES, statuses=APPEAL_STATUSES, filters=filters, sort_url=sort_url, page_url=page_url, sort=sort, order=order)


@app.route('/cabinet/appeal/<int:appeal_id>', methods=['GET', 'POST'])
@login_required
def appeal_detail(appeal_id):
    if current_user.is_staff:
        return redirect(url_for('staff_appeal_detail', appeal_id=appeal_id))

    appeal = user_appeals_query(current_user).filter_by(id=appeal_id).first_or_404()
    history = AppealStatusHistory.query.filter_by(appeal_id=appeal.id).order_by(AppealStatusHistory.changed_at.desc()).all()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'upload':
            save_appeal_files(appeal, request.files.getlist('files'))
            db.session.commit()
            flash('Документы добавлены.', 'success')
        elif action == 'rate' and appeal.status == 'closed' and not appeal.rating:
            rating = request.form.get('rating')
            if rating in RATING_OPTIONS:
                db.session.add(AppealRating(appeal_id=appeal.id, rating=rating, comment=request.form.get('comment', '').strip()))
                db.session.commit()
                flash('Оценка отправлена.', 'success')
        return redirect(url_for('appeal_detail', appeal_id=appeal.id))

    return render_template('appeal_detail.html', appeal=appeal, history=history, rating_options=RATING_OPTIONS)


@app.route('/staff')
@staff_required
def staff_panel():
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    sort = request.args.get('sort', 'date_submitted')
    order = request.args.get('order', 'desc')
    page = request.args.get('page', 1, type=int)

    query = apply_appeal_filters(Appeal.query, category, status, date_from, date_to)
    sort_column = SORT_COLUMNS.get(sort, Appeal.date_submitted)
    query = query.order_by(sort_column.asc() if order == 'asc' else sort_column.desc())
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    filters = {'category': category, 'status': status, 'date_from': date_from, 'date_to': date_to, 'sort': sort, 'order': order}

    def sort_url(column):
        new_order = 'asc' if sort == column and order == 'desc' else 'desc' if sort == column else 'asc'
        return build_staff_url(category=category, status=status, date_from=date_from, date_to=date_to, sort=column, order=new_order, page=1)

    def page_url(page_num):
        return build_staff_url(category=category, status=status, date_from=date_from, date_to=date_to, sort=sort, order=order, page=page_num)

    return render_template(
        'staff_panel.html',
        appeals=pagination.items,
        pagination=pagination,
        categories=APPEAL_CATEGORIES,
        statuses=APPEAL_STATUSES,
        filters=filters,
        sort_url=sort_url,
        page_url=page_url,
        sort=sort,
        order=order,
    )


@app.route('/staff/appeal/<int:appeal_id>', methods=['GET', 'POST'])
@staff_required
def staff_appeal_detail(appeal_id):
    appeal = Appeal.query.get_or_404(appeal_id)
    history = AppealStatusHistory.query.filter_by(appeal_id=appeal.id).order_by(AppealStatusHistory.changed_at.desc()).all()

    if request.method == 'POST':
        new_status = request.form.get('status', '')
        comment = request.form.get('comment', '').strip()
        if new_status not in APPEAL_STATUSES:
            flash('Выберите корректный статус.', 'danger')
        elif new_status == appeal.status and not comment:
            flash('Укажите комментарий или выберите другой статус.', 'danger')
        else:
            appeal.status = new_status
            add_status_history(appeal, new_status, comment or f'Статус изменён на «{APPEAL_STATUSES[new_status]}»')
            db.session.commit()
            flash('Статус обращения обновлён.', 'success')
        return redirect(url_for('staff_appeal_detail', appeal_id=appeal.id))

    return render_template(
        'staff_appeal_detail.html',
        appeal=appeal,
        history=history,
        statuses=APPEAL_STATUSES,
        rating_options=RATING_OPTIONS,
    )


@app.route('/files/<int:file_id>')
@login_required
def download_file(file_id):
    file = AppealFile.query.get_or_404(file_id)
    appeal = Appeal.query.get_or_404(file.appeal_id)
    if not can_access_appeal(appeal, current_user):
        flash('Доступ запрещён.', 'danger')
        return redirect(home_url_for_user(current_user))
    return send_from_directory(app.config['UPLOAD_FOLDER'], file.stored_name, as_attachment=True, download_name=file.original_name)


@app.route('/admin/test-email')
def admin_test_email():
    admin_key = os.getenv('ADMIN_RESET_KEY', '').strip()
    if not admin_key or request.args.get('key', '') != admin_key:
        return 'Неверный ADMIN_RESET_KEY.', 403
    to_addr = request.args.get('to', '').strip().lower() or os.getenv('EMAIL_USER', '').strip()
    if not to_addr:
        return 'Укажите ?to=ваш@gmail.com', 400
    ok = send_email(to_addr, 'Тест — МО МВД', 'Если вы видите это письмо — отправка работает.')
    lines = [
        f'Отправка на {to_addr}: {"OK" if ok else "ОШИБКА"}',
        f'RENDER free (SMTP заблокирован): {is_render_free_smtp_blocked()}',
        f'RESEND_API_KEY: {"да" if os.getenv("RESEND_API_KEY", "").strip() else "нет"}',
    ]
    if not ok and get_last_email_error():
        lines.append(f'Причина: {get_last_email_error()}')
    return '<br>'.join(lines), (200 if ok else 500)


@app.route('/admin/verify-staff-email')
def admin_verify_staff_email():
    admin_key = os.getenv('ADMIN_RESET_KEY', '').strip()
    if not admin_key:
        return 'Задайте ADMIN_RESET_KEY в .env или Render.', 404
    if request.args.get('key', '') != admin_key:
        return 'Неверный ключ.', 403
    email = request.args.get('email', '').strip().lower()
    if not email:
        return 'Укажите ?key=...&email=адрес@mail.ru', 400
    user = User.query.filter_by(email=email).first()
    if not user:
        return f'Пользователь {email} не найден.', 404
    if email not in STAFF_EMAILS:
        return 'Этот email не в списке служебных.', 403
    user.role = 'staff'
    user.email_verified = True
    user.email_verify_code = None
    user.email_verify_expires = None
    db.session.commit()
    flash('Email сотрудника подтверждён. Войдите в систему.', 'success')
    return redirect(url_for('login'))


@app.route('/admin/setup-staff')
def admin_setup_staff():
    admin_key = os.getenv('ADMIN_RESET_KEY', '').strip()
    if not admin_key or request.args.get('key', '') != admin_key:
        return 'Неверный или отсутствует ADMIN_RESET_KEY.', 403
    email = request.args.get('email', '').strip().lower()
    password = request.args.get('password', '').strip()
    if not email:
        return 'Укажите: ?key=КЛЮЧ&email=oktyabrsky28@gmail.com&password=ВашПароль123', 400
    if email not in STAFF_EMAILS:
        return 'Этот email не разрешён для сотрудника.', 403
    pwd_error = validate_password(password)
    if pwd_error:
        return f'Пароль не подходит: {pwd_error}', 400
    user = User.query.filter_by(email=email).first()
    if not user:
        return f'Сначала зарегистрируйтесь на сайте как сотрудник ({email}).', 404
    user.role = 'staff'
    user.email_verified = True
    user.email_verify_code = None
    user.email_verify_expires = None
    user.set_password(password)
    db.session.commit()
    flash(f'Сотрудник {email} настроен. Войдите с новым паролем.', 'success')
    return redirect(url_for('login'))


@app.route('/admin/clear-database', methods=['GET', 'POST'])
def admin_clear_database():
    """Очистка БД по секретному ключу (без платного Shell на Render)."""
    admin_key = os.getenv('ADMIN_RESET_KEY', '').strip()
    if not admin_key:
        return 'Сервис отключён: задайте ADMIN_RESET_KEY в Environment.', 404

    provided = request.args.get('key', '') or request.form.get('key', '')
    if provided != admin_key:
        return 'Неверный ключ.', 403

    if request.method == 'POST' and request.form.get('confirm') == 'yes':
        users, appeals = clear_all_data()
        flash(f'Удалено: {users} пользователей и {appeals} обращений.', 'success')
        return redirect(url_for('index'))

    return f'''
    <!DOCTYPE html>
    <html lang="ru"><head><meta charset="UTF-8"><title>Очистка базы</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head><body class="p-4"><div class="container" style="max-width:480px">
    <h4>Очистить все аккаунты и обращения?</h4>
    <p class="text-danger">Действие необратимо.</p>
    <form method="POST">
    <input type="hidden" name="key" value="{escape(provided)}">
    <input type="hidden" name="confirm" value="yes">
    <button type="submit" class="btn btn-danger">Да, удалить всё</button>
    <a href="/" class="btn btn-secondary ms-2">Отмена</a>
    </form></div></body></html>
    '''


with app.app_context():
    try:
        migrate_db()
    except Exception as e:
        print('Ошибка миграции БД:', e)


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    print('Internal Server Error:', error)
    flash('Внутренняя ошибка сервера. Попробуйте ещё раз или обратитесь к администратору.', 'danger')
    return redirect(url_for('index')), 500


if __name__ == '__main__':
    debug = os.getenv('FLASK_DEBUG', '1') == '1'
    port = int(os.getenv('PORT', '5000'))
    print(f'Сайт запущен: http://127.0.0.1:{port}')
    app.run(host='0.0.0.0', port=port, debug=debug)
