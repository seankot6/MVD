import os
import random
import re
import secrets
import smtplib
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import uuid4

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

RECIPIENT_EMAIL = 'oktyabrsky28@gmail.com'
STAFF_EMAILS = {RECIPIENT_EMAIL.lower()}
PER_PAGE = 10
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


def send_email(to_email, subject, body):
    email_user = os.getenv('EMAIL_USER')
    email_pass = os.getenv('EMAIL_PASS')
    if not email_user or not email_pass:
        print('Ошибка почты: не заданы EMAIL_USER или EMAIL_PASS')
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=20)
        server.starttls()
        server.login(email_user, email_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print('Ошибка почты:', e)
        return False


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
    """Сохраняет код в БД и отправляет письмо. Пользователь уже должен быть в базе."""
    user.email_verify_code = generate_email_verify_code()
    user.email_verify_expires = datetime.utcnow() + timedelta(minutes=15)
    user.email_verified = False
    body = (
        f'Код подтверждения регистрации: {user.email_verify_code}\n\n'
        'Введите его на странице подтверждения email.\n'
        'Код действует 15 минут.'
    )
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print('Ошибка сохранения кода:', e)
        return False
    if send_email(user.email, 'Код подтверждения — МО МВД Октябрьский', body):
        return True
    print('Письмо с кодом не отправлено на', user.email)
    return False


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


@app.route('/')
def index():
    return render_template('home.html')


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
            flash('Пользователь с таким email уже зарегистрирован.', 'danger')
            return redirect(url_for('register'))

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
                db.session.commit()
                email_sent = issue_email_verify_code(user)
                if email_sent:
                    flash('На ваш email отправлен 6-значный код. Введите его для завершения регистрации.', 'info')
                else:
                    flash(
                        'Аккаунт создан, но письмо не ушло. На следующей странице нажмите '
                        '«Отправить код повторно» или проверьте EMAIL_USER / EMAIL_PASS в Render → Environment.',
                        'warning',
                    )
                return redirect(url_for('register_verify', email=email))

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
            if issue_email_verify_code(user):
                flash('Новый код отправлен на email.', 'info')
            else:
                flash('Не удалось отправить код. Попробуйте позже.', 'danger')
            return redirect(url_for('register_verify', email=email))

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

    return render_template('register_verify.html', email=email, masked_email=mask_email(email) if email else '')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(home_url_for_user(current_user))
    if request.method == 'POST':
        login_value = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        user = find_user_by_login(login_value)
        if user and user.check_password(password):
            if user.is_staff and not user.email_verified:
                flash('Подтвердите email — введите код из письма.', 'warning')
                return redirect(url_for('register_verify', email=user.email))
            login_user(user, remember=remember)
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(home_url_for_user(user))
        flash('Неверный email, телефон или пароль.', 'danger')
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
            else:
                flash(
                    'Аккаунт найден, но письмо не отправлено. На сервере не настроена почта '
                    '(EMAIL_USER / EMAIL_PASS в Render → Environment). Обратитесь к администратору.',
                    'danger',
                )
        else:
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
