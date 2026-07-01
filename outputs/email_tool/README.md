# Email Sending Tool

This folder contains a small SMTP-based email sender for Codex automation outputs.

## 1. Configure credentials

Copy `email.env.example` to `email.env`, then fill in the real values:

```sh
cp email.env.example email.env
```

Or set these environment variables in the terminal that will run the sender:

```sh
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USE_STARTTLS="true"
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-16-character-app-password"
export EMAIL_FROM="your-email@gmail.com"
export EMAIL_TO="kennethoseinimako@gmail.com"
```

For Gmail, use a Google App Password. Your normal Gmail password usually will not work for SMTP.

The real `email.env` file is ignored by git so your SMTP password is not accidentally tracked.

## 2. Send a dry-run test

```sh
python3 send_email.py --subject "Codex test" --body "This is a dry run." --dry-run
```

## 3. Send a real test

```sh
python3 send_email.py --subject "Codex test" --body "Email sending is configured."
```

## 4. Use with generated text

```sh
python3 send_email.py --subject "NHS Band 3 sponsorship alert" --body-file alert.txt
```

## 5. Send a styled jobs-board email

```sh
python3 send_email.py \
  --subject "NHS Band 3 sponsorship alert" \
  --body-file todays_nhs_notification.txt \
  --html-file todays_nhs_notification.html
```

When `--html-file` is provided, the email is sent as multipart HTML with the text file as the fallback.
