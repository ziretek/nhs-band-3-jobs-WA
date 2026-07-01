# NHS Band 3 Jobs with Visa Sponsorship — WhatsApp Alert

Searches NHS Jobs daily for Band 3 positions that welcome Skilled Worker visa sponsorship, then sends the results to your WhatsApp.

## How it works

1. **Scrapes** `nhs_today_alert.py` scans [NHS Jobs](https://www.jobs.nhs.uk) for:
   - Band 3 roles with "visa sponsorship" keyword
   - Healthcare Assistant roles (all bands)
2. **Filters** — excludes listings that say sponsorship is unavailable or require existing right to work
3. **Sends** results to your WhatsApp via CallMeBot

## One-time setup

### 1. Set up CallMeBot (free, no API keys)

1. Open WhatsApp on your phone
2. Send a message to **+34 632 50 06 78**
3. Message must be exactly: `I allow callmebot to send me messages`
4. You'll receive a reply with your **API key** — save it

### 2. Add secrets to GitHub

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret | Value |
|--------|-------|
| `CALLMEBOT_PHONE` | Your phone number with country code. For a UK number: `447123456789` (omit the + and spaces) |
| `CALLMEBOT_APIKEY` | The API key you received from CallMeBot |

### 3. Run it

- **Automatic:** The workflow runs daily at 8:00 AM UTC
- **Manual:** Go to **Actions → NHS Daily Alert → Run workflow**

## Files

| Path | Purpose |
|------|---------|
| `work/nhs_today_alert.py` | NHS Jobs scraper for visa sponsorship roles |
| `work/send_whatsapp.py` | WhatsApp sender (supports CallMeBot & Cloud API) |
| `outputs/email_tool/send_email.py` | Alternative email sender (SMTP) |
| `.github/workflows/nhs-alert.yml` | GitHub Actions scheduled workflow |
