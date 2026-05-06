---
name: refresh-ig-session
description: >
  Refreshes the Instagram instagrapi session for the Mieshania bot.
  Use when the bot reports "Instagram session expired", when ig_session.json
  needs to be regenerated, or when asked to refresh/update the Instagram session.
allowed-tools: shell
---

# Refresh Instagram Session for Mieshania Bot

This skill refreshes the `ig_session.json` file used by the bot to access Instagram
via instagrapi, then deploys it to the VPS.

## Important

**Must be run from a residential IP** (home Wi-Fi or mobile hotspot).
Do NOT run from VPS or datacenter IPs — Instagram blocks logins from those.

## How to run

Run the interactive refresh script from the repo root:

```bash
python refresh_ig_session.py
```

The script will:
1. Ask for Instagram credentials (or read from `.env`)
2. Log in as `solov__design`
3. Save the session to `ig_session.json`
4. Offer to SCP the file to VPS (`root@91.98.134.12:/var/opt/mieshania/ig_session.json`)
5. Offer to restart the bot (`systemctl restart mieshania`)

## Manual steps (if the script fails)

```bash
python -c "
from instagrapi import Client
import json
cl = Client()
cl.delay_range = [1, 3]
cl.login('solov__design', '<PASSWORD>')
print('Logged in as:', cl.username)
open('ig_session.json', 'w').write(json.dumps(cl.get_settings()))
print('Session saved.')
"
scp ig_session.json root@91.98.134.12:/var/opt/mieshania/ig_session.json
ssh root@91.98.134.12 "systemctl restart mieshania && systemctl is-active mieshania"
```

## Session lifespan

Sessions typically last **2–4 weeks**. When the Telegram bot sends admin alert:

> ⚠️ Instagram сесія Мєшані протухла!

...it's time to run this skill.

## VPS details

- Host: `root@91.98.134.12`
- Session path: `/var/opt/mieshania/ig_session.json`
- Bot service: `mieshania`
- Bot logs: `/var/log/mieshania.downloader.log`
