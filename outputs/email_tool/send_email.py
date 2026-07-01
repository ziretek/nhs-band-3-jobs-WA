#!/usr/bin/env python3
"""Send an email using SMTP settings from environment variables."""

from __future__ import annotations

import argparse
import html
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path


def load_env_file() -> None:
    env_path = Path(os.environ.get("EMAIL_ENV_FILE", Path(__file__).with_name("email.env")))
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(name, value)


def env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value or ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send an email via SMTP.")
    parser.add_argument("--to", default=os.environ.get("EMAIL_TO"), help="Recipient email address")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--body", help="Email body text")
    parser.add_argument("--body-file", help="Path to a text file to use as the email body")
    parser.add_argument("--html", help="HTML email body")
    parser.add_argument("--html-file", help="Path to an HTML file to use as the email body")
    parser.add_argument("--dry-run", action="store_true", help="Print the message without sending")
    return parser.parse_args()


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as content_file:
        return content_file.read()


def html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?</\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</(p|div|tr|h[1-6]|li)>", "\n", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n\s*", "\n\n", value)
    return value.strip() + "\n"


def read_body(args: argparse.Namespace) -> tuple[str, str | None]:
    html_body = None
    if args.html_file:
        html_body = read_file(args.html_file)
    elif args.html:
        html_body = args.html

    if args.body_file:
        return read_file(args.body_file), html_body
    if args.body is not None:
        return args.body, html_body
    if html_body is not None:
        return html_to_text(html_body), html_body
    if not sys.stdin.isatty():
        return sys.stdin.read(), html_body
    raise SystemExit("Provide --body, --body-file, --html-file, or pipe message text on stdin.")


def build_message(args: argparse.Namespace, body: str, html_body: str | None) -> EmailMessage:
    sender = env("EMAIL_FROM") or env("SMTP_USERNAME", required=True)
    recipient = args.to
    if not recipient:
        raise SystemExit("Provide --to or set EMAIL_TO.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = args.subject

    reply_to = env("EMAIL_REPLY_TO")
    if reply_to:
        message["Reply-To"] = reply_to

    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    return message


def send_message(message: EmailMessage) -> None:
    host = env("SMTP_HOST", required=True)
    port = int(env("SMTP_PORT", "587"))
    username = env("SMTP_USERNAME")
    password = env("SMTP_PASSWORD")
    use_ssl = env("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes"}
    use_starttls = env("SMTP_USE_STARTTLS", "true").lower() in {"1", "true", "yes"}

    context = ssl.create_default_context()
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=context) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
        return

    with smtplib.SMTP(host, port) as smtp:
        smtp.ehlo()
        if use_starttls:
            smtp.starttls(context=context)
            smtp.ehlo()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)


def main() -> None:
    load_env_file()
    args = parse_args()
    body, html_body = read_body(args)
    message = build_message(args, body, html_body)

    if args.dry_run:
        print(message)
        return

    send_message(message)
    print(f"Sent email to {message['To']}")


if __name__ == "__main__":
    main()
