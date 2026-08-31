from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from vox_sentry import sound
from vox_sentry.sound import (
    MAX_NOTIFICATION_SOUND_DURATION,
    MAX_NOTIFICATION_SOUND_SIZE,
    SoundValidationError,
    validate_notification_sound,
)

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is required for audio fixtures")


def make_audio(path: Path, duration: float = 0.35, *options: str) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=44100",
            "-t",
            str(duration),
            "-ac",
            "1",
            *options,
            str(path),
        ],
        check=True,
    )
    return path


@pytest.fixture
def valid_audio(tmp_path: Path) -> dict[str, Path]:
    return {
        "mp3": make_audio(tmp_path / "valid.mp3", 0.35, "-c:a", "libmp3lame", "-b:a", "128k"),
        "ogg": make_audio(tmp_path / "valid.ogg", 0.35, "-c:a", "libvorbis", "-q:a", "4"),
        "oga": make_audio(tmp_path / "valid.oga", 0.35, "-c:a", "libvorbis", "-q:a", "4"),
        "wav": make_audio(tmp_path / "valid.wav", 0.35, "-c:a", "pcm_s16le"),
        "flac": make_audio(tmp_path / "valid.flac", 0.35, "-c:a", "flac"),
    }


def assert_code(path: Path, code: str) -> None:
    with pytest.raises(SoundValidationError) as error:
        validate_notification_sound(path)
    assert error.value.code == code


def test_all_supported_formats_validate(valid_audio: dict[str, Path]) -> None:
    metadata = {format_name: validate_notification_sound(path) for format_name, path in valid_audio.items()}
    assert set(metadata) == {"mp3", "ogg", "oga", "wav", "flac"}
    assert all(item.duration > 0 for item in metadata.values())


@pytest.mark.parametrize("bitrate", ["32k", "320k"])
def test_mp3_valid_low_and_high_bitrate(tmp_path: Path, bitrate: str) -> None:
    path = make_audio(tmp_path / f"mp3-{bitrate}.mp3", 0.4, "-c:a", "libmp3lame", "-b:a", bitrate)
    assert validate_notification_sound(path).format_name == "mp3"


def test_mp3_valid_vbr(tmp_path: Path) -> None:
    path = make_audio(tmp_path / "mp3-vbr.mp3", 0.4, "-c:a", "libmp3lame", "-q:a", "4")
    assert validate_notification_sound(path).format_name == "mp3"


def test_mp3_exactly_ten_seconds_is_allowed(tmp_path: Path) -> None:
    path = make_audio(tmp_path / "mp3-10s.mp3", MAX_NOTIFICATION_SOUND_DURATION, "-c:a", "libmp3lame", "-b:a", "128k")
    assert validate_notification_sound(path).duration <= MAX_NOTIFICATION_SOUND_DURATION + 0.05


def test_mp3_above_ten_seconds_is_rejected(tmp_path: Path) -> None:
    path = make_audio(tmp_path / "mp3-too-long.mp3", MAX_NOTIFICATION_SOUND_DURATION + 0.5, "-c:a", "libmp3lame", "-b:a", "128k")
    assert_code(path, "duration")


def test_mp3_below_five_mb_is_allowed(tmp_path: Path) -> None:
    path = make_audio(tmp_path / "mp3-small.mp3", 1, "-c:a", "libmp3lame", "-b:a", "128k")
    assert path.stat().st_size < MAX_NOTIFICATION_SOUND_SIZE
    assert validate_notification_sound(path).size < MAX_NOTIFICATION_SOUND_SIZE


def test_mp3_above_five_mb_is_rejected(tmp_path: Path) -> None:
    path = make_audio(tmp_path / "mp3-large.mp3", 0.4, "-c:a", "libmp3lame", "-b:a", "128k")
    with path.open("ab") as file:
        file.write(b"\0" * (MAX_NOTIFICATION_SOUND_SIZE - path.stat().st_size + 1))
    assert_code(path, "size")


def test_corrupt_and_empty_mp3_are_rejected(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.mp3"
    corrupt.write_bytes(b"ID3 this is not audio")
    assert_code(corrupt, "mime-mismatch")
    empty = tmp_path / "empty.mp3"
    empty.touch()
    assert_code(empty, "empty")


def test_text_renamed_to_mp3_and_wrong_mime_are_rejected(tmp_path: Path) -> None:
    text = tmp_path / "notification.mp3"
    text.write_text("this is not an MP3\n", encoding="utf-8")
    assert_code(text, "magic")
    valid_ogg = make_audio(tmp_path / "valid.ogg", 0.3, "-c:a", "libvorbis", "-q:a", "4")
    wrong_extension = tmp_path / "audio.mp3"
    shutil.copyfile(valid_ogg, wrong_extension)
    assert_code(wrong_extension, "magic")


def test_valid_mp3_with_no_decoder_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = make_audio(tmp_path / "decoder.mp3", 0.3, "-c:a", "libmp3lame", "-b:a", "64k")
    original_which = sound.shutil.which
    monkeypatch.setattr(sound.shutil, "which", lambda name: None if name == "ffprobe" else original_which(name))
    with pytest.raises(SoundValidationError) as error:
        validate_notification_sound(path)
    assert error.value.code == "decoder-unavailable"


def test_removed_custom_sound_is_rejected_and_can_fallback(tmp_path: Path) -> None:
    removed = tmp_path / "removed.mp3"
    removed.write_bytes(b"ID3")
    removed.unlink()
    assert_code(removed, "missing")
