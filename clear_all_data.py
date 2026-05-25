"""
Удалить всех пользователей и все обращения.
Локально:  .\\venv\\Scripts\\python.exe clear_all_data.py
На Render: Shell → python clear_all_data.py
"""
from app import app, clear_all_data


def clear_all():
    with app.app_context():
        users, appeals = clear_all_data()
        print(f'Удалено: {users} пользователей, {appeals} обращений.')


if __name__ == '__main__':
    clear_all()
