from flask import Flask, render_template_string, request, redirect, flash
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = "diploma-mvd-oktyabrsky-2026"

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

RECIPIENT_EMAIL = "oktyabrsky28@gmail.com"

def send_appeal_email(data, is_anonymous, photo_path=None):
    try:
        msg = MIMEMultipart()
        msg['From'] = os.getenv('EMAIL_USER')
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = f"Новое обращение {'(Анонимно)' if is_anonymous else ''} — МО МВД Октябрьский"

        body = f"""
Новое обращение в МО МВД Октябрьский

Анонимно: {'Да' if is_anonymous else 'Нет'}
ФИО: {data.get('full_name', '—')}
Телефон: {data.get('phone', '—')}
Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

Текст:
{data.get('appeal_text', '')}
        """
        msg.attach(MIMEText(body, 'plain'))

        if photo_path and os.path.exists(photo_path):
            with open(photo_path, "rb") as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(photo_path)}"')
                msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print("Ошибка почты:", e)
        return False


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        is_anonymous = request.form.get('anonymous') == 'on'
        full_name = request.form.get('full_name', '')
        phone = request.form.get('phone', '')
        appeal_text = request.form.get('appeal_text', '')

        photo_path = None
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo.filename:
                photo_path = os.path.join(UPLOAD_FOLDER, photo.filename)
                photo.save(photo_path)

        send_appeal_email({'full_name': full_name, 'phone': phone, 'appeal_text': appeal_text}, is_anonymous, photo_path)

        flash('✅ Спасибо за ваше обращение! С вами свяжется сотрудник полиции.', 'success')
        return redirect('/')

    return render_template_string('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>МО МВД Октябрьский</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #f0f4f8; }
        .header { 
            background: linear-gradient(135deg, #0033a0, #0066ff); 
            color: white; 
            padding: 25px 0; 
        }
        .sidebar { 
            background: white; 
            border-radius: 12px; 
            box-shadow: 0 5px 15px rgba(0,0,0,0.1); 
            padding: 20px;
        }
        input[type="file"] {
            padding: 10px;
            border: 2px dashed #0066ff;
            background: #f8f9fa;
            border-radius: 8px;
            width: 100%;
        }
    </style>
</head>
<body>
    <!-- Шапка без логотипа -->
    <div class="header">
        <div class="container text-center">
            <h3 class="mb-1">МВД РОССИИ</h3>
            <h5>Межмуниципальный отдел по Октябрьскому району</h5>
        </div>
    </div>

    <div class="container mt-4">
        <div class="row">
            
            <!-- Левая колонка -->
            <div class="col-lg-3">
                <div class="sidebar mb-4">
                    <h5 class="text-primary mb-3">📍 Адрес</h5>
                    <p><strong>с. Екатеринославка</strong><br>
                       ул. Коммунальная, 57</p>
                    
                    <hr>
                    <h5 class="text-primary mb-3">🕒 Часы работы</h5>
                    <p><strong>Приём обращений:</strong><br>
                       Понедельник — Пятница: 09:00 — 18:00<br>
                       Обед: 13:00 — 14:00</p>
                    
                    <hr>
                    <h5 class="text-primary mb-3">📞 Контакты</h5>
                    <p><strong>Дежурная часть:</strong><br>
                       +7 (416) 522-52-22</p>
                    <p><strong>Единый номер:</strong> 102 или 112</p>
                </div>
            </div>

            <!-- Центральная форма -->
            <div class="col-lg-6">
                <div class="card shadow">
                    <div class="card-header bg-primary text-white text-center">
                        <h4>Подать обращение в МВД Октябрьский</h4>
                    </div>
                    <div class="card-body p-4">
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for cat, msg in messages %}
                                    <div class="alert alert-{{ cat }}">{{ msg }}</div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}

                        <form method="POST" enctype="multipart/form-data">
                            <div class="mb-4 form-check form-switch">
                                <input class="form-check-input" type="checkbox" id="anonymous" name="anonymous" onchange="toggleFields()">
                                <label class="form-check-label fw-bold" for="anonymous">Подать обращение анонимно</label>
                            </div>

                            <div id="user-fields">
                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <label>ФИО <span class="text-danger">*</span></label>
                                        <input type="text" name="full_name" class="form-control">
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <label>Телефон <span class="text-danger">*</span></label>
                                        <input type="tel" name="phone" class="form-control">
                                    </div>
                                </div>
                            </div>

                            <div class="mb-4">
                                <label>Текст обращения <span class="text-danger">*</span></label>
                                <textarea name="appeal_text" class="form-control" rows="7" required></textarea>
                            </div>

                            <div class="mb-4">
                                <label>Прикрепить фото или документ</label>
                                <input type="file" name="photo" class="form-control">
                            </div>

                            <button type="submit" class="btn btn-primary btn-lg w-100">Отправить обращение</button>
                        </form>
                    </div>
                </div>
            </div>

            <!-- Правая колонка -->
            <div class="col-lg-3">
                <div class="sidebar p-4">
                    <h5 class="text-primary mb-3">📰 Новости полиции</h5>
                    <div class="mb-3">
                        <strong>05.05.2026</strong><br>
                        <small>Проведён рейд по профилактике ДТП в с. Екатеринославка</small>
                    </div>
                    <div class="mb-3">
                        <strong>03.05.2026</strong><br>
                        <small>Напоминаем о необходимости регистрации транспортных средств</small>
                    </div>
                    <div class="mb-3">
                        <strong>01.05.2026</strong><br>
                        <small>Усилены меры безопасности в майские праздники</small>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function toggleFields() {
            var isAnon = document.getElementById('anonymous').checked;
            document.getElementById('user-fields').style.display = isAnon ? 'none' : 'block';
        }
    </script>
</body>
</html>
    ''')

if __name__ == '__main__':
    print("✅ Сайт запущен без логотипа!")
    app.run(host='0.0.0.0', port=5000, debug=True)