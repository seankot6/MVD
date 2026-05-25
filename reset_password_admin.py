"""
Сброс пароля пользователя в локальной базе (на вашем ПК).
Запуск:
  .\venv\Scripts\python.exe reset_password_admin.py email@example.com НовыйПароль123
"""
import sys

from app import app, db
from models import User


def main():
    if len(sys.argv) != 3:
        print('Использование: python reset_password_admin.py email@example.com НовыйПароль')
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    password = sys.argv[2]

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f'Пользователь {email} не найден в локальной базе.')
            print('На Render — другая база: зарегистрируйтесь заново или настройте почту там.')
            sys.exit(1)
        user.set_password(password)
        user.email_verified = True
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        print(f'Пароль для {email} обновлён (локальная база).')


if __name__ == '__main__':
    main()
