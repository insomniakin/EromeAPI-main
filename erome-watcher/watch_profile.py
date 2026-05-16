from __future__ import annotations

import argparse
import json
from pathlib import Path

from erome_watcher.alerts import format_alert
from erome_watcher.client import EromeClient
from erome_watcher.state import diff_and_update


def main() -> None:
    parser = argparse.ArgumentParser(description='Check an Erome profile and emit a diff JSON report.')
    parser.add_argument('username', help='Erome username/profile path segment')
    parser.add_argument('--state-dir', default=str(Path(__file__).resolve().parent / 'state'))
    parser.add_argument('--format', choices=['json', 'telegram', 'discord', 'summary'], default='json')
    args = parser.parse_args()

    client = EromeClient()
    snapshot = client.get_profile_snapshot(args.username)
    diff = diff_and_update(snapshot, Path(args.state_dir))
    if args.format == 'json':
        print(json.dumps(diff.model_dump(), indent=2))
        return
    alert = format_alert(diff)
    if args.format == 'telegram':
        print(alert.telegram_text)
    elif args.format == 'discord':
        print(alert.discord_text)
    else:
        print(alert.summary)


if __name__ == '__main__':
    main()
