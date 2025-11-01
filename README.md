# Mieshania Telegram Bot 🐭
A Telegram chat bot written in **Python 3 + aiogram**, designed for fun group interactions: random jokes, roasts, morning messages, and air alert notifications (via alerts.in.ua).

> ⚠️ This repository is sanitized — it contains no API keys, no cookies, and no private data.  
> To run it, you must create your own `.env` file and cookies locally.

## 🧩 Features
- `/joke` — random or GPT-generated Ukrainian joke
- `/roast @user` — personal roast from the local pool
- `/coin`, `/dice`, `/roll`, `/rps`, `/slot` — fun mini-commands
- `/air_status`, `/air_on_kyiv`, `/air_on_region` — air alert integration
- Persistent MySQL/MariaDB storage for chats and joke history

## ⚙️ Requirements
- **Python 3.10+**
- **MySQL / MariaDB**
- **pip**, **virtualenv**
- Optional: OpenAI API key, Alerts.in.ua API token

## 🚀 Quick Setup
1. Clone repo:
```bash
git clone https://github.com/yourusername/mieshania.git
cd mieshania
```
2. Create venv & install deps:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
3. Copy `.env.example` to `.env` and fill your values.
4. Create MySQL/MariaDB database:
```sql
CREATE DATABASE mieshania CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'mieshania_user'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON mieshania.* TO 'mieshania_user'@'localhost';
FLUSH PRIVILEGES;
```
5. Import schema:
```bash
mysql -u mieshania_user -p mieshania < sql/schema.sql
```
6. Run bot:
```bash
python bot.py
```
