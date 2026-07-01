# NHS Band 3, 4 and 5 Jobs with Visa Sponsorship — Telegram Alert

Searches NHS Jobs daily for permanent, full-time Band 3, Band 4 and Band 5 positions that welcome Skilled Worker visa sponsorship, then sends the results to Telegram.

## How it works

1. **Scrapes** `nhs_today_alert.py` scans [NHS Jobs](https://www.jobs.nhs.uk) for:
   - Band 3 roles with "visa sponsorship" keyword
   - Band 4 roles with "visa sponsorship" keyword
   - Band 5 roles with "visa sponsorship" keyword
2. **Filters** — requires a permanent contract and a working pattern that includes full-time, then excludes listings that deny or cannot guarantee sponsorship. Generic NHS sponsorship boilerplate is not treated as proof that a role is eligible.
3. **Sends** results to your Telegram account through a private bot

## One-time setup

### 1. Create a Telegram bot

1. Open Telegram and start a chat with **@BotFather**.
2. Send `/newbot` and follow the prompts.
3. Save the bot token BotFather gives you.
4. Open your new bot and send it `/start` so it is allowed to message you.
5. Send another message such as `hello`, then open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and copy the numeric `message.chat.id` value.

### 2. Add secrets to GitHub

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret | Value |
|--------|-------|
| `TELEGRAM_BOT_TOKEN` | The token received from BotFather |
| `TELEGRAM_CHAT_ID` | The numeric chat ID returned by `getUpdates` |

### 3. Run it

- **Automatic:** The workflow runs daily at 8:00 AM UTC
- **Manual:** Go to **Actions → NHS Daily Alert → Run workflow**

## Files

| Path | Purpose |
|------|---------|
| `work/nhs_today_alert.py` | NHS Jobs scraper for visa sponsorship roles |
| `work/send_telegram.py` | Telegram Bot API sender |
| `work/send_whatsapp.py` | Legacy WhatsApp sender |
| `outputs/email_tool/send_email.py` | Alternative email sender (SMTP) |
| `.github/workflows/nhs-alert.yml` | GitHub Actions scheduled workflow |
