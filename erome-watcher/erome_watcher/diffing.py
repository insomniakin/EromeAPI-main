from __future__ import annotations

from .models import ProfileDiff, ProfileSnapshot


def diff_profile_snapshots(previous: ProfileSnapshot, current: ProfileSnapshot) -> ProfileDiff:
    prev_map = {album.id: album for album in previous.albums}
    curr_map = {album.id: album for album in current.albums}

    new_ids = [album_id for album_id in curr_map if album_id not in prev_map]
    removed_ids = [album_id for album_id in prev_map if album_id not in curr_map]
    unchanged_count = sum(1 for album_id in curr_map if album_id in prev_map)

    return ProfileDiff(
        username=current.username,
        previous_album_count=previous.album_count,
        current_album_count=current.album_count,
        new_albums=[curr_map[album_id] for album_id in new_ids],
        removed_albums=[prev_map[album_id] for album_id in removed_ids],
        unchanged_count=unchanged_count,
    )
