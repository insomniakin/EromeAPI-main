#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description='POST an Erome watcher alert to a Hermes webhook endpoint.')
    parser.add_argument('webhook_url')
    parser.add_argument('username')
    parser.add_argument('--api-base', default='http://127.0.0.1:8011')
    args = parser.parse_args()

    with httpx.Client(timeout=60) as client:
        alert = client.post(f'{args.api_base}/watch/alert', json={'username': args.username, 'persist': True})
        alert.raise_for_status()
        payload = alert.json()
        response = client.post(args.webhook_url, json=payload)
        response.raise_for_status()

    print(json.dumps({'posted': True, 'webhook_url': args.webhook_url, 'username': args.username}, indent=2))


if __name__ == '__main__':
    main()
