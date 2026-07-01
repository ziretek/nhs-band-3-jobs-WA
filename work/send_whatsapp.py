#!/usr/bin/env python3
"""Send a text message via WhatsApp (supports CallMeBot or WhatsApp Cloud API)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error


CALLMEBOT_CHUNK_SIZE = 800
CALLMEBOT_DELAY_SECONDS = 10
CALLMEBOT_MAX_ATTEMPTS = 3
RETRYABLE_HTTP_CODES = {403, 429, 500, 502, 503, 504}


def send_via_callmebot(phone: str, apikey: str, body: str) -> dict:
    """Send via callmebot.com — free, no business account needed."""
    params = urllib.parse.urlencode({
        "phone": phone,
        "text": body,
        "apikey": apikey,
    })
    url = f"https://api.callmebot.com/whatsapp.php?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,*/*",
            "User-Agent": "Mozilla/5.0 NHS-Jobs-WhatsApp-Alert/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return {"status": response.status, "body": response.read().decode("utf-8")}


def send_via_cloud_api(access_token: str, phone_number_id: str, to: str, body: str) -> dict:
    """Send via Meta WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def chunk_text(text: str, max_len: int = 4096) -> list[str]:
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["callmebot", "cloud-api"], default="callmebot")

    # CallMeBot
    parser.add_argument("--phone", default=os.environ.get("CALLMEBOT_PHONE", ""))
    parser.add_argument("--apikey", default=os.environ.get("CALLMEBOT_APIKEY", ""))

    # Cloud API
    parser.add_argument("--access-token", default=os.environ.get("WA_ACCESS_TOKEN", ""))
    parser.add_argument("--phone-number-id", default=os.environ.get("WA_PHONE_NUMBER_ID", ""))
    parser.add_argument("--to", default=os.environ.get("WA_TO", ""))

    parser.add_argument("--body", default="")
    parser.add_argument("--body-file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.method == "callmebot":
        if not args.phone or not args.apikey:
            print("Missing CallMeBot credentials. Set CALLMEBOT_PHONE and CALLMEBOT_APIKEY.", file=sys.stderr)
            sys.exit(1)
    else:
        if not all([args.access_token, args.phone_number_id, args.to]):
            print("Missing Cloud API credentials.", file=sys.stderr)
            sys.exit(1)

    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()
    else:
        body = args.body

    if not body:
        print("No message body provided.", file=sys.stderr)
        sys.exit(1)

    max_len = CALLMEBOT_CHUNK_SIZE if args.method == "callmebot" else 4096
    chunks = chunk_text(body, max_len=max_len)

    if args.dry_run:
        print(f"[DRY RUN] Would send {len(chunks)} message(s)")
        for i, chunk in enumerate(chunks, 1):
            preview = chunk[:200] + "..." if len(chunk) > 200 else chunk
            print(f"\n--- Chunk {i} ({len(chunk)} chars) ---")
            print(preview)
        return

    for i, chunk in enumerate(chunks, 1):
        if args.method == "callmebot":
            for attempt in range(1, CALLMEBOT_MAX_ATTEMPTS + 1):
                try:
                    result = send_via_callmebot(args.phone, args.apikey, chunk)
                    print(f"Sent chunk {i}/{len(chunks)} — status: {result['status']}")
                    break
                except urllib.error.HTTPError as e:
                    error_body = e.read().decode("utf-8", errors="replace")
                    if e.code not in RETRYABLE_HTTP_CODES or attempt == CALLMEBOT_MAX_ATTEMPTS:
                        print(f"Failed chunk {i}: HTTP {e.code} — {error_body}", file=sys.stderr)
                        sys.exit(1)
                    delay = CALLMEBOT_DELAY_SECONDS * attempt
                    print(
                        f"CallMeBot returned HTTP {e.code} for chunk {i}; "
                        f"retrying in {delay}s ({attempt}/{CALLMEBOT_MAX_ATTEMPTS}).",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
                except urllib.error.URLError as e:
                    if attempt == CALLMEBOT_MAX_ATTEMPTS:
                        print(f"Failed chunk {i}: {e.reason}", file=sys.stderr)
                        sys.exit(1)
                    delay = CALLMEBOT_DELAY_SECONDS * attempt
                    print(
                        f"CallMeBot connection failed for chunk {i}; "
                        f"retrying in {delay}s ({attempt}/{CALLMEBOT_MAX_ATTEMPTS}).",
                        file=sys.stderr,
                    )
                    time.sleep(delay)

            # CallMeBot rate-limits requests, including requests from separate
            # workflow steps, so pause after the final chunk as well.
            time.sleep(CALLMEBOT_DELAY_SECONDS)
        else:
            try:
                result = send_via_cloud_api(args.access_token, args.phone_number_id, args.to, chunk)
                print(f"Sent chunk {i}/{len(chunks)} — ID: {result.get('messages', [{}])[0].get('id', 'unknown')}")
            except urllib.error.HTTPError as e:
                print(f"Failed chunk {i}: HTTP {e.code} — {e.read().decode('utf-8', errors='replace')}", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
