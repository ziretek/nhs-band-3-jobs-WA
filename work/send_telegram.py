#!/usr/bin/env python3
"""Send a text alert through the Telegram Bot API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


TELEGRAM_CHUNK_SIZE = 4000
MAX_ATTEMPTS = 3
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


def chunk_text(text: str, max_len: int = TELEGRAM_CHUNK_SIZE) -> list[str]:
    """Split text at natural boundaries without exceeding max_len."""
    remaining = text.strip()
    chunks: list[str] = []

    while len(remaining) > max_len:
        split_at = remaining.rfind("\n", 0, max_len + 1)
        if split_at <= 0:
            split_at = remaining.rfind(" ", 0, max_len + 1)
        if split_at <= 0:
            split_at = max_len

        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()

    if remaining:
        chunks.append(remaining)
    return chunks


def send_message(token: str, chat_id: str, text: str) -> dict:
    """Send one Telegram message and return the decoded API response."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram returned an unsuccessful response"))
    return result


def retry_delay(error_body: str, attempt: int) -> int:
    """Use Telegram's retry_after value when available."""
    try:
        response = json.loads(error_body)
        return max(int(response.get("parameters", {}).get("retry_after", 0)), attempt * 5)
    except (TypeError, ValueError, json.JSONDecodeError):
        return attempt * 5


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default=os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    parser.add_argument("--chat-id", default=os.environ.get("TELEGRAM_CHAT_ID", ""))
    parser.add_argument("--body", default="")
    parser.add_argument("--body-file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.token or not args.chat_id:
        print(
            "Missing Telegram credentials. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.body_file:
        with open(args.body_file, encoding="utf-8") as body_file:
            body = body_file.read()
    else:
        body = args.body

    if not body:
        print("No message body provided.", file=sys.stderr)
        sys.exit(1)

    chunks = chunk_text(body)
    if args.dry_run:
        print(f"[DRY RUN] Would send {len(chunks)} Telegram message(s)")
        print("Chunk sizes:", ", ".join(str(len(chunk)) for chunk in chunks))
        return

    for index, chunk in enumerate(chunks, 1):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                result = send_message(args.token, args.chat_id, chunk)
                message_id = result["result"]["message_id"]
                print(f"Sent Telegram chunk {index}/{len(chunks)} — message ID: {message_id}")
                break
            except urllib.error.HTTPError as error:
                error_body = error.read().decode("utf-8", errors="replace")
                if error.code not in RETRYABLE_HTTP_CODES or attempt == MAX_ATTEMPTS:
                    print(
                        f"Failed Telegram chunk {index}: HTTP {error.code} — {error_body}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                delay = retry_delay(error_body, attempt)
                print(
                    f"Telegram returned HTTP {error.code}; retrying in {delay}s "
                    f"({attempt}/{MAX_ATTEMPTS}).",
                    file=sys.stderr,
                )
                time.sleep(delay)
            except urllib.error.URLError as error:
                if attempt == MAX_ATTEMPTS:
                    print(f"Telegram connection failed: {error.reason}", file=sys.stderr)
                    sys.exit(1)
                delay = attempt * 5
                print(
                    f"Telegram connection failed; retrying in {delay}s "
                    f"({attempt}/{MAX_ATTEMPTS}).",
                    file=sys.stderr,
                )
                time.sleep(delay)

        if index < len(chunks):
            time.sleep(1)


if __name__ == "__main__":
    main()
