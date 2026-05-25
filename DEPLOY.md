# Публикация сайта в интернет (домен + телефон + работа 24/7)

Сейчас сайт работает только пока на компьютере запущен `python app.py`.  
Чтобы он был **всегда доступен** с телефона и любого устройства, нужен **хостинг в интернете**.

## Бесплатно через GitHub (рекомендуется для диплома)

См. подробную пошаговую инструкцию: **[DEPLOY-GITHUB-RENDER.md](DEPLOY-GITHUB-RENDER.md)**  
Репозиторий проекта: **https://github.com/seankot6/MVD**

Полноценный **бесплатный домен .ru** надёжно почти не выдают. Обычно бесплатно дают **поддомен хостинга** или нужно купить домен (~200–500 ₽/год).

---

## Что уже готово в проекте

- Адаптивная вёрстка (Bootstrap + стили для телефона)
- Запуск через **Gunicorn** (`wsgi.py`, `Procfile`)
- Настройки для HTTPS за Nginx (`BEHIND_PROXY`, `SESSION_COOKIE_SECURE`)

---

## Шаг 1. Купить домен

Регистраторы (РФ): **reg.ru**, **Timeweb**, **nic.ru**, **beget.com**

Пример: `obrascheniya-mvd.ru` или поддомен для диплома.

В панели регистратора позже укажете **A-запись** на IP вашего сервера.

---

## Шаг 2. Арендовать VPS (сервер)

Минимум: **1 GB RAM**, Ubuntu 22.04/24.04.

Провайдеры: Timeweb, Selectel, reg.ru, Aeza, Beget VPS.

После создания сервера вы получите **IP-адрес** (например `185.12.34.56`).

В DNS домена:

| Тип | Имя | Значение |
|-----|-----|----------|
| A | @ | IP сервера |
| A | www | IP сервера |

---

## Шаг 3. Загрузить проект на сервер

На сервере (SSH):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx git

sudo mkdir -p /var/www/citizen-appeals
sudo chown $USER:$USER /var/www/citizen-appeals
```

Скопируйте папку проекта на сервер (WinSCP, FileZilla или `git clone`).

```bash
cd /var/www/citizen-appeals
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # SECRET_KEY, EMAIL_USER, EMAIL_PASS, FLASK_ENV=production
```

Сгенерируйте секретный ключ:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Создайте папки:

```bash
mkdir -p instance uploads
```

---

## Шаг 4. Запуск как службы (всегда работает)

```bash
sudo cp deploy/citizen-appeals.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable citizen-appeals
sudo systemctl start citizen-appeals
sudo systemctl status citizen-appeals
```

Сайт слушает `127.0.0.1:8000` — снаружи пока не открыт, нужен Nginx.

---

## Шаг 5. Nginx + HTTPS (ваш домен)

```bash
sudo cp deploy/nginx-site.conf /etc/nginx/sites-available/citizen-appeals
sudo nano /etc/nginx/sites-available/citizen-appeals
# замените your-domain.ru на ваш домен и путь к static

sudo ln -s /etc/nginx/sites-available/citizen-appeals /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

sudo certbot --nginx -d your-domain.ru -d www.your-domain.ru
```

После этого сайт открывается: **https://ваш-домен.ru** с телефона и ПК, без запуска проекта на домашнем ПК.

---

## Бесплатный вариант: GitHub + Render

### Что можно и что нельзя

| Способ | Бесплатно? | Подходит для вашего Flask-сайта? |
|--------|------------|----------------------------------|
| **GitHub Pages** | Да | **Нет** — только статические HTML-страницы, без Python и базы |
| **GitHub + Render / Railway** | Да* | **Да** — репозиторий на GitHub, сайт крутится на Render |
| **Бесплатный домен .tk / .ml (Freenom)** | Раньше да | Сейчас по сути **не работает** |
| **Свой домен .ru** | Нет (~200–500 ₽/год) | Да, можно привязать к Render |

\* Бесплатный план Render: сайт «засыпает» без посетителей 15+ мин (первый заход — пауза ~30 сек). Для диплома обычно достаточно.

### Пошагово (0 ₽, без VPS)

1. Зарегистрируйтесь на [github.com](https://github.com) и [render.com](https://render.com).
2. Создайте репозиторий, загрузите проект (без папки `venv` и без файла `.env`).
3. На Render: **New → Blueprint** → подключите репозиторий (в корне есть `render.yaml`).
4. В Render в **Environment** добавьте переменные:
   - `EMAIL_USER` — ваша почта Gmail
   - `EMAIL_PASS` — пароль приложения Gmail
5. После деплоя получите адрес: **`https://имя-сервиса.onrender.com`** — им можно делиться и открывать с телефона.

### Свой домен к бесплатному хостингу

Купленный домен (reg.ru и т.д.) можно привязать в Render: **Settings → Custom Domains** — бесплатный SSL выдаст сам Render.

### Ограничение бесплатного Render

База SQLite на бесплатном диске **может сброситься** при пересборке сервиса. Для защиты данных делайте копию `instance/appeals.db`. Для серьёзной работы — VPS или платный диск на Render.

### Другие бесплатные хостинги (аналогично GitHub)

- **Railway** — подключается к GitHub, даёт поддомен `*.up.railway.app`
- **Fly.io** — есть бесплатный лимит
- **PythonAnywhere** — бесплатный тариф с ограничениями

Код тот же: `gunicorn` + `wsgi.py` + переменные из `.env.example`.

---

## Альтернатива без своего сервера (проще, но свой домен сложнее)

**Railway / Render / PythonAnywhere** — загружаете проект, получаете адрес вида `app.onrender.com`.

Свой домен часто подключается в настройках хостинга (CNAME).

`Procfile` уже есть: `web: gunicorn ...`

---

## Важно для продакшена

1. **SECRET_KEY** — уникальный, не из примера.
2. **`.env`** — не публикуйте в интернет.
3. Резервная копия: `instance/appeals.db` и папка `uploads/`.
4. Gmail: используйте **пароль приложения**, не обычный пароль.

---

## Локально vs в интернете

| | Дома (`python app.py`) | На сервере |
|---|---|---|
| Доступ | Только пока ПК включён | 24/7 |
| Адрес | `127.0.0.1:5000` | `https://ваш-домен.ru` |
| Телефон вне дома | Нет* | Да |

\*Если не пробрасывать порт на роутере (для диплома лучше VPS).
