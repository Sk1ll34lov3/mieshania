# Mieshania Telegram Bot 🐭

A multifunctional **Telegram bot** written in **Python 3 + aiogram**, designed for fun group chats:  
jokes, roasts, media downloads, morning alarms, and air alert notifications via [alerts.in.ua](https://alerts.in.ua).

> ⚠️ This repository is sanitized — it contains **no API keys, cookies, or private data**.  
> You must create your own `.env` file and cookies locally.

---

## 🧩 Features Overview

Mieshania supports multiple command groups with role-based access (default, private, group, admin).

---

### 🧍 [Default Commands]

| Command | Description |
|----------|--------------|
| `/help` | Show help |
| `/ping` | Check bot status |
| `/id` | Show your `chat_id` |
| `/get` | Download video (YouTube / TikTok / Instagram) |
| `/joke` | Random joke (GPT or custom pool) |
| `/roast` | Roast a tagged user |
| `/rps` | Rock–Paper–Scissors |
| `/slot` | 🎰 Slot machine |
| `/random_on` | Enable random joke posting |
| `/random_off` | Disable random joke posting |
| `/random_window` | Set random joke interval (minutes) |
| `/mode` | Set joke tone: `pg13` or `r18` |
| `/quiet` | Set quiet hours or disable them |
| `/morning_on` | Enable morning wake-up messages |
| `/morning_off` | Disable morning wake-up messages |
| `/morning_time` | Set wake-up time (HH:MM) |
| `/joke_add` | Add a joke to your local pool |
| `/joke_list` | List all jokes |
| `/joke_rm` | Remove a joke by ID |
| `/air_on_kyiv` | Enable air alerts for Kyiv city |
| `/air_off_kyiv` | Disable air alerts for Kyiv city |
| `/air_on_region` | Enable alerts for Kyiv region |
| `/air_off_region` | Disable alerts for Kyiv region |
| `/air_status` | Get current air alert status |
| `/set_title` | Assign a custom title to @user |
| `/title` | Show current user title |

---

### 💬 [Private Chats]

Identical command set for 1-on-1 usage.  
All `/joke`, `/get`, `/air_status` and `/mode` commands function in private chat as well.

---

### 👥 [Groups]

Same as default, with automatic group-specific database tracking (`chat_id` based).  
Random joke scheduler and morning wake-up are designed primarily for groups.

---

### 🔧 [Admins]

| Command | Description |
|----------|-------------|
| `/warn` | Warn @user (3 warns = auto mute for 30 min) |
| `/mute` | Mute @user for specified minutes |
| `/unmute` | Unmute @user |
| `/ban` | Ban @user |
| `/kick` | Kick @user from group |

---

## ⚙️ Requirements

- **Python 3.10+**
- **MySQL / MariaDB** (recommended 10.5+)
- **pip**, **virtualenv**
- Optional: OpenAI API key for GPT jokes
- Optional: Alerts.in.ua API token for air alerts

---

## 🗂 Project structure

```
mieshania/
│
├── bot.py
├── config.py
├── requirements.txt
├── .env.example
├── /handlers/
│   ├── fun.py
│   ├── alerts.py
│   ├── schedule.py
│   └── moderation.py
├── /services/
│   ├── joke.py
│   ├── air_alerts.py
│   ├── db.py
│   └── utils.py
├── /sql/
│   └── schema.sql
└── README.md
```

---

## 🚀 Setup Instructions

1️⃣ **Clone the repository:**
```bash
git clone https://github.com/yourusername/mieshania.git
cd mieshania
```

2️⃣ **Create virtual environment and install dependencies:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3️⃣ **Create and configure `.env`:**
```bash
cp .env.example .env
```
Edit the `.env` file with your bot token, database credentials, and API keys.

4️⃣ **Create database:**
```sql
CREATE DATABASE mieshania CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'mieshania_user'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON mieshania.* TO 'mieshania_user'@'localhost';
FLUSH PRIVILEGES;
```

5️⃣ **Import schema:**
```bash
mysql -u mieshania_user -p mieshania < sql/schema.sql
```

6️⃣ **Run the bot:**
```bash
python bot.py
```

---

## 🧰 Environment Variables (`.env.example`)

```env
# Telegram
BOT_TOKEN=your_telegram_bot_token_here

# Database
DB_HOST=localhost
DB_PORT=3306
DB_NAME=mieshania
DB_USER=mieshania_user
DB_PASS=your_password

# Alerts.in.ua
ALERTS_TOKEN=your_alerts_in_ua_token_here

# OpenAI (optional)
OPENAI_API_KEY=sk-...

# Joke generator
GPT_JOKES_ON=1
GPT_JOKES_MODEL=gpt-4o-mini
GPT_JOKES_TEMP=0.9
GPT_JOKES_PROB=0.6

# Cookies paths (optional)
COOKIES_INSTAGRAM_PATH=./cookies_instagram.txt
COOKIES_TIKTOK_PATH=./cookies_tiktok.txt
COOKIES_YOUTUBE_PATH=./cookies_youtube.txt
COOKIES_PATH=./cookies.txt
```

---

## 🧱 Database Schema

See [`sql/schema.sql`](sql/schema.sql) — it includes:
- `chats` — per-chat settings  
- `jokes` — general jokes  
- `jokes_personal` — personalized roast templates  
- `joke_history` — GPT and user joke logs  

---

## 🛠 Systemd Example

For VPS (Ubuntu):

```ini
[Unit]
Description=Mieshania Telegram Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/mieshania
EnvironmentFile=/opt/mieshania/.env
ExecStart=/opt/mieshania/.venv/bin/python /opt/mieshania/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 🧹 Notes

- Never commit `.env` or `cookies*.txt`
- Each user must create their own `.env` and cookies locally
- Use your own Telegram bot token (create via [@BotFather](https://t.me/BotFather))
- Database name can be arbitrary (default `mieshania`)
- Recommended Python version: **3.11+**

---

## 🐛 Debugging

If something fails:
```bash
tail -n 100 /var/log/mieshania.log
```

Run manually with verbose mode:
```bash
python bot.py --debug
```

---

Enjoy building and customizing your **Mieshania Bot** 🐭🔥  
The funniest, darkest Telegram companion your group ever had.
