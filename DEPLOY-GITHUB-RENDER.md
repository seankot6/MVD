# Пошаговая публикация: GitHub + Render (бесплатно)

Инструкция для проекта **citizen-appeals** на Windows.  
В конце сайт будет открываться по адресу вида `https://что-то.onrender.com` с телефона и ПК, **без** запуска `python app.py` дома.

У вас уже есть репозиторий: **https://github.com/seankot6/MVD**

---

## Часть 1. Подготовка проекта на компьютере

### 1.1. Что нельзя выкладывать на GitHub

| Файл / папка | Почему |
|--------------|--------|
| `.env` | Пароли и секреты |
| `venv/` | Тяжёлая, ставится на сервере заново |
| `instance/appeals.db` | Личные данные, своя база на сервере |
| `uploads/*` (кроме `.gitkeep`) | Загруженные файлы пользователей |
| `__pycache__/` | Служебные файлы Python |

В проекте уже есть `.gitignore` — он это скрывает.

### 1.2. Пароль приложения Gmail (для писем с кодом)

1. Google-аккаунт → **Безопасность** → **Двухэтапная аутентификация** (включить).
2. **Пароли приложений** → создать для «Почта» / «Другое».
3. Скопировать 16-символьный пароль — это будет `EMAIL_PASS` (не обычный пароль от Gmail).

### 1.3. Секретный ключ для сайта

В PowerShell в папке проекта:

```powershell
cd "C:\Users\Пользователь\citizen-appeals"
.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Скопируйте строку — понадобится на Render как `SECRET_KEY`.

---

## Часть 2. Загрузка кода на GitHub

### 2.1. Откройте терминал в папке проекта

```powershell
cd "C:\Users\Пользователь\citizen-appeals"
```

### 2.2. Проверьте, что секреты не попадут в git

```powershell
git status
```

В списке **не должно** быть `.env` и `instance/appeals.db`.  
Если `.env` виден — не добавляйте его; проверьте `.gitignore`.

### 2.3. Добавьте файлы и сделайте коммит

```powershell
git add .
git status
```

Убедитесь, что в коммит **не** входят `.env`, `venv`, `instance/appeals.db`.

```powershell
git commit -m "Подготовка к публикации на Render"
```

### 2.4. Отправьте на GitHub

```powershell
git push origin main
```

Если GitHub попросит вход — войдите в браузере или используйте [Personal Access Token](https://github.com/settings/tokens) вместо пароля.

Проверьте: на https://github.com/seankot6/MVD должны появиться файлы `render.yaml`, `wsgi.py`, `app.py`, папки `templates`, `static`.

---

## Часть 3. Регистрация на Render

1. Откройте https://render.com  
2. **Get Started** → войдите через **GitHub** (удобнее всего).  
3. Разрешите Render доступ к репозиториям.  
4. Можно выбрать только репозиторий **MVD**, если спросит.

---

## Часть 4. Создание сайта на Render

### Способ А — через Blueprint (проще, если есть `render.yaml`)

1. В Render: **New +** → **Blueprint**.  
2. Подключите репозиторий **seankot6/MVD**.  
3. Render найдёт `render.yaml` и предложит создать сервис **citizen-appeals**.  
4. Перед деплоем откройте **Environment** и добавьте вручную (если их нет):

| Ключ | Значение |
|------|----------|
| `EMAIL_USER` | ваш Gmail, например `oktyabrsky28@gmail.com` |
| `EMAIL_PASS` | пароль приложения Gmail (16 символов) |

`SECRET_KEY` Render может сгенерировать сам (в `render.yaml` указано `generateValue: true`).

5. **Apply** / **Create** — начнётся сборка (5–15 минут).

### Способ Б — вручную (если Blueprint не сработал)

1. **New +** → **Web Service**.  
2. Репозиторий **MVD** → Connect.  
3. Настройки:

| Поле | Значение |
|------|----------|
| Name | `citizen-appeals` (или любое) |
| Region | Frankfurt / ближайший к вам |
| Branch | `main` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn -w 2 -b 0.0.0.0:$PORT wsgi:app` |
| Plan | **Free** |

4. **Environment Variables** — добавьте все:

```
PYTHON_VERSION = 3.12.0
FLASK_ENV = production
FLASK_DEBUG = 0
BEHIND_PROXY = 1
SESSION_COOKIE_SECURE = 1
SECRET_KEY = (строка из шага 1.3)
EMAIL_USER = ваш@gmail.com
EMAIL_PASS = пароль приложения Gmail
```

5. **Create Web Service**.

---

## Часть 5. Дождаться деплоя

1. Вкладка **Logs** — смотрите процесс.  
2. Успех: в логах что-то вроде `Listening at: http://0.0.0.0:10000` и статус **Live**.  
3. Вверху появится ссылка: **`https://citizen-appeals-xxxx.onrender.com`** (имя может отличаться).

Откройте её в браузере и на телефоне.

### Если сборка упала

| Ошибка в логах | Что сделать |
|----------------|-------------|
| `ModuleNotFoundError` | Проверьте `requirements.txt` в репозитории |
| `No module named 'app'` | Start Command должен быть `gunicorn ... wsgi:app` |
| Письма не уходят | Проверьте `EMAIL_USER` / `EMAIL_PASS` на Render |
| 502 / долго грузится | Бесплатный план «просыпается» — подождите 30–60 сек |

---

## Часть 6. После публикации

### Регистрация сотрудника на сервере

На Render база **новая и пустая**. Нужно снова:

1. **Регистрация** → «Я сотрудник МО МВД» → служебный email.  
2. Ввести код из письма (Gmail должен быть настроен в переменных Render).

### Обновление сайта после изменений в коде

На компьютере:

```powershell
git add .
git commit -m "Описание изменений"
git push origin main
```

Render **сам пересоберёт** сайт (1–10 минут). Локально `python app.py` для интернета больше не нужен.

### Резервная копия базы на Render

На бесплатном тарифе при пересборке данные SQLite **могут пропасть**. Для диплома сохраняйте копию `instance/appeals.db` у себя на ПК после важных тестов.

---

## Часть 7. Свой домен (необязательно, платно)

1. Купить домен на reg.ru / Timeweb (~200–500 ₽/год).  
2. В Render: ваш сервис → **Settings** → **Custom Domains** → Add.  
3. Render покажет, какие **DNS-записи** добавить у регистратора (обычно CNAME).  
4. Через 15–60 минут сайт откроется по `https://ваш-домен.ru`.

Бесплатный адрес `*.onrender.com` продолжит работать параллельно.

---

## Часть 8. Сравнение: до и после

| | Дома | GitHub + Render |
|---|------|-----------------|
| Запуск | `python app.py` каждый раз | Не нужен |
| Адрес | `http://127.0.0.1:5000` | `https://....onrender.com` |
| Телефон вне дома | Нет | Да |
| Стоимость | 0 ₽ | 0 ₽ (бесплатный план) |
| Первый заход после простоя | — | Может ждать ~30 сек |

---

## Краткий чеклист

- [ ] `.env` не в GitHub  
- [ ] `git push` на https://github.com/seankot6/MVD  
- [ ] Аккаунт Render + подключён GitHub  
- [ ] Web Service или Blueprint, Start: `gunicorn -w 2 -b 0.0.0.0:$PORT wsgi:app`  
- [ ] Переменные `SECRET_KEY`, `EMAIL_USER`, `EMAIL_PASS`  
- [ ] Статус **Live**, ссылка открывается с телефона  
- [ ] Регистрация и вход проверены на боевом сайте  

Если застрянете на конкретном шаге — напишите, на каком (номер шага и текст ошибки из Render Logs).
