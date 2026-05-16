from __future__ import annotations

from .models import AlertMessage, ProfileDiff


def _album_lines(albums: list, bullet: str = '- ') -> list[str]:
    lines = []
    for album in albums[:10]:
        title = album.title or album.id
        lines.append(f"{bullet}{title} — {album.url}")
    if len(albums) > 10:
        lines.append(f"{bullet}... and {len(albums) - 10} more")
    return lines


def format_alert(diff: ProfileDiff) -> AlertMessage:
    parts = [
        f"Erome update for {diff.username}",
        f"Albums: {diff.previous_album_count} -> {diff.current_album_count}",
    ]
    if diff.new_albums:
        parts.append(f"New albums: {len(diff.new_albums)}")
        parts.extend(_album_lines(diff.new_albums))
    if diff.removed_albums:
        parts.append(f"Removed albums: {len(diff.removed_albums)}")
        parts.extend(_album_lines(diff.removed_albums))
    if not diff.new_albums and not diff.removed_albums:
        parts.append("No changes detected")

    summary = '\n'.join(parts)
    telegram = '\n'.join([
        f"🔎 Erome update: {diff.username}",
        f"Albums: {diff.previous_album_count} → {diff.current_album_count}",
        *( [f"🆕 New: {len(diff.new_albums)}"] + _album_lines(diff.new_albums, '• ') if diff.new_albums else [] ),
        *( [f"🗑 Removed: {len(diff.removed_albums)}"] + _album_lines(diff.removed_albums, '• ') if diff.removed_albums else [] ),
        *( ["No changes detected"] if not diff.new_albums and not diff.removed_albums else [] ),
    ])
    discord = '\n'.join([
        f"**Erome update:** `{diff.username}`",
        f"Albums: **{diff.previous_album_count} → {diff.current_album_count}**",
        *( [f"**New albums:** {len(diff.new_albums)}"] + _album_lines(diff.new_albums) if diff.new_albums else [] ),
        *( [f"**Removed albums:** {len(diff.removed_albums)}"] + _album_lines(diff.removed_albums) if diff.removed_albums else [] ),
        *( ["No changes detected"] if not diff.new_albums and not diff.removed_albums else [] ),
    ])

    return AlertMessage(
        username=diff.username,
        summary=summary,
        telegram_text=telegram,
        discord_text=discord,
        new_album_count=len(diff.new_albums),
        removed_album_count=len(diff.removed_albums),
    )
