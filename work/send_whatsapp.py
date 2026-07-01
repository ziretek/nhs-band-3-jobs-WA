#!/usr/bin/env python3
"""Send a text message via WhatsApp Cloud API (Meta)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error


API_VERSION = "v22.0"
BASE = "https://graph.facebook.com"


def send_message(
    access_token: str,
    phone_number_id: str,
    to: str,
    body: str,
) -> dict:
    url = f"{BASE}/{API_VERSION}/{phone_number_id}/messages"
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
    """Split long text into WhatsApp-safe chunks (max 4096 chars each)."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--access-token", default=os.environ.get("WA_ACCESS_TOKEN", ""))
    parser.add_argument("--phone-number-id", default=os.environ.get("WA_PHONE_NUMBER_ID", ""))
    parser.add_argument("--to", default=os.environ.get("WA_TO", ""))
    parser.add_argument("--body", default="")
    parser.add_argument("--body-file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not all([args.access_token, args.phone_number_id, args.to]):
        print("Missing required arguments. Set WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID, WA_TO", file=sys.stderr)
        sys.exit(1)

    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()
    else:
        body = args.body

    if not body:
        print("No message body provided.", file=sys.stderr)
        sys.exit(1)

    chunks = chunk_text(body)

    if args.dry_run:
        print(f"[DRY RUN] Would send {len(chunks)} message(s) to {args.to}")
        for i, chunk in enumerate(chunks, 1):
            print(f"\n--- Chunk {i} ({len(chunk)} chars) ---")
            print(chunk[:200] + "..." if len(chunk) > 200 else chunk)
        return

    for i, chunk in enumerate(chunks, 1):
        try:
            result = send_message(args.access_token, args.phone_number_id, args.to, chunk)
            print(f"Sent chunk {i}/{len(chunks)} — message ID: {result.get('messages', [{}])[0].get('id', 'unknown')}")
        except urllib.error.HTTPError as e:
            print(f"Failed chunk {i}: HTTP {e.code} — {e.read().decode('utf-8', errors='replace')}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
