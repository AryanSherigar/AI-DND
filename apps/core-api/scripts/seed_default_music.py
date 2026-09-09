"""One-time script: upload the 6 canonical default mood tracks to storage.

Run once per environment (dev/staging/prod) whenever a default track
changes. Expects one file per mood (peaceful, mystery, tension, combat,
melancholy, triumph) in the given directory, matched case-insensitively by
filename stem -- MP3 only, matching the fixed object keys in
app/services/default_music.py.

Usage: python -m scripts.seed_default_music /path/to/audio/dir
"""

import asyncio
import sys
from pathlib import Path

from app.db.models.scenario_music import MOOD_SLOTS
from app.integrations import storage_client
from app.services import default_music

_CONTENT_TYPE = "audio/mpeg"


def _find_source_file(source_dir: Path, mood: str) -> Path:
    for candidate in source_dir.iterdir():
        if candidate.is_file() and candidate.stem.lower() == mood:
            return candidate
    raise FileNotFoundError(f"No .mp3 file found for mood '{mood}' in {source_dir}")


async def _seed_mood(source_dir: Path, mood: str) -> None:
    source_file = _find_source_file(source_dir, mood)

    content = source_file.read_bytes()
    object_key = f"default-music/{mood}.mp3"
    uploaded_url = await storage_client.upload_image(content, _CONTENT_TYPE, object_key)

    expected_url = default_music.default_track_url(mood)
    if uploaded_url != expected_url:
        raise RuntimeError(
            f"Uploaded URL for '{mood}' ({uploaded_url}) does not match the "
            f"canonical URL ({expected_url}). Check default_music.py's "
            "object keys match this script's upload keys."
        )
    print(f"Seeded {mood}: {uploaded_url}")


async def _seed_all(source_dir: Path) -> None:
    for mood in MOOD_SLOTS:
        await _seed_mood(source_dir, mood)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.seed_default_music /path/to/audio/dir")
        sys.exit(1)

    source_dir = Path(sys.argv[1])
    if not source_dir.is_dir():
        print(f"Not a directory: {source_dir}")
        sys.exit(1)

    asyncio.run(_seed_all(source_dir))


if __name__ == "__main__":
    main()
