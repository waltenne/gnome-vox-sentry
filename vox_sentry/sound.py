"""Validation helpers for notification sounds.

The GNOME extension performs the final GStreamer validation and playback.  This
module mirrors the same policy for the CLI/tests so invalid files are rejected
before they reach the player.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

MAX_NOTIFICATION_SOUND_DURATION = 10.0
# MPEG audio is frame based; a file encoded for exactly ten seconds can carry
# one final padded frame (normally a few milliseconds). This is container
# padding, not extra user audio, so allow a small decoder-reporting tolerance.
_DURATION_PADDING_TOLERANCE = 0.05
MAX_NOTIFICATION_SOUND_SIZE = 5 * 1024 * 1024
SUPPORTED_NOTIFICATION_SOUND_FORMATS = ("mp3", "ogg", "oga", "wav", "flac")

SUPPORTED_NOTIFICATION_SOUND_MIME_TYPES = {
    "mp3": {"audio/mpeg", "audio/mp3", "audio/x-mpeg"},
    "ogg": {"audio/ogg", "application/ogg", "audio/x-ogg", "audio/x-vorbis+ogg", "audio/x-opus+ogg"},
    "oga": {"audio/ogg", "application/ogg", "audio/x-ogg", "audio/x-vorbis+ogg", "audio/x-opus+ogg"},
    "wav": {"audio/wav", "audio/x-wav", "audio/vnd.wave", "audio/wave"},
    "flac": {"audio/flac", "audio/x-flac"},
}


class SoundValidationError(ValueError):
    """A sound cannot be accepted by the notification sound policy."""

    def __init__(self, message: str, *, code: str, format_name: str | None = None) -> None:
        super().__init__(message)
        self.code, self.format_name = code, format_name


@dataclass(frozen=True)
class NotificationSoundMetadata:
    path: Path
    format_name: str
    mime_type: str
    duration: float
    size: int


def _format_for_path(path: Path) -> str:
    suffix = path.suffix.lower().removeprefix(".")
    if suffix not in SUPPORTED_NOTIFICATION_SOUND_FORMATS:
        raise SoundValidationError(
            "Supported formats: MP3, OGG, OGA, WAV and FLAC",
            code="unsupported-format",
            format_name=suffix or None,
        )
    return suffix


def _mime_type(path: Path) -> str:
    file_command = shutil.which("file")
    if not file_command:
        raise SoundValidationError("Unable to determine the audio MIME type.", code="mime-unavailable")
    result = subprocess.run(
        [file_command, "--brief", "--mime-type", "--", str(path)],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    )
    mime = result.stdout.strip().lower()
    if result.returncode != 0 or not re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", mime):
        raise SoundValidationError("Unable to determine the audio MIME type.", code="mime-invalid")
    return mime


def _mp3_frame_length(data: bytes, index: int) -> int | None:
    if index + 4 > len(data):
        return None
    header = int.from_bytes(data[index : index + 4], "big")
    if header >> 21 != 0x7FF:
        return None
    version = (header >> 19) & 0x3
    layer = (header >> 17) & 0x3
    bitrate_index = (header >> 12) & 0xF
    sample_rate_index = (header >> 10) & 0x3
    if version == 1 or layer == 0 or bitrate_index in (0, 15) or sample_rate_index == 3:
        return None
    bitrates = {
        (3, 3): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 0],
        (3, 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0],
        (3, 1): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
        (2, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0],
        (2, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
        (2, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
        (0, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0],
        (0, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
        (0, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
    }
    sample_rates = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}
    bitrate = bitrates[(version, layer)][bitrate_index] * 1000
    sample_rate = sample_rates[version][sample_rate_index]
    padding = (header >> 9) & 1
    if layer == 3:
        return ((12 * bitrate // sample_rate) + padding) * 4
    return (144 * bitrate // sample_rate) + padding if version == 3 else (72 * bitrate // sample_rate) + padding


def _has_mp3_frame(data: bytes) -> bool:
    if data.startswith(b"ID3"):
        return True
    # Require a legal frame followed by another frame at the calculated frame
    # boundary. This avoids treating random Ogg payload bytes as MP3 headers.
    for index in range(max(0, min(len(data) - 3, 4096))):
        length = _mp3_frame_length(data, index)
        if length and _mp3_frame_length(data, index + length):
            return True
    return False


def _magic_matches(format_name: str, data: bytes) -> bool:
    if format_name == "mp3":
        return _has_mp3_frame(data)
    if format_name in {"ogg", "oga"}:
        return data.startswith(b"OggS")
    if format_name == "wav":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if format_name == "flac":
        return data.startswith(b"fLaC")
    return False


def _decode_and_probe(path: Path, format_name: str) -> tuple[float, str]:
    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        raise SoundValidationError(
            "Required multimedia decoder is not available.",
            code="decoder-unavailable",
            format_name=format_name,
        )
    probe = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name",
            "-of",
            "json",
            "--",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    try:
        payload = json.loads(probe.stdout)
        duration = float(payload["format"]["duration"])
        detected_formats = str(payload["format"].get("format_name", "")).split(",")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SoundValidationError(
            "The audio file is corrupt or cannot be decoded.", code="decode", format_name=format_name
        ) from exc
    if probe.returncode != 0 or not math.isfinite(duration) or duration <= 0:
        raise SoundValidationError(
            "The audio file is corrupt or cannot be decoded.", code="decode", format_name=format_name
        )
    expected_container = {"mp3": {"mp3"}, "ogg": {"ogg"}, "oga": {"ogg"}, "wav": {"wav"}, "flac": {"flac"}}[format_name]
    if not expected_container.intersection(detected_formats):
        raise SoundValidationError(
            "The file content does not match its extension.", code="content-mismatch", format_name=format_name
        )
    decoded = subprocess.run(
        [ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    if decoded.returncode != 0:
        error = (decoded.stderr or "").lower()
        missing_decoder = any(token in error for token in ("decoder", "codec", "unknown format", "not found"))
        raise SoundValidationError(
            "Required multimedia decoder is not available." if missing_decoder else "The audio file is corrupt or cannot be decoded.",
            code="decoder-unavailable" if missing_decoder else "decode",
            format_name=format_name,
        )
    return duration, detected_formats[0]


def validate_notification_sound(path: str | Path) -> NotificationSoundMetadata:
    """Validate extension, MIME, magic, size, duration and real decoding."""

    sound_path = Path(path).expanduser()
    format_name = _format_for_path(sound_path)
    if not sound_path.is_file():
        raise SoundValidationError("The selected audio file does not exist.", code="missing", format_name=format_name)
    size = sound_path.stat().st_size
    if size <= 0:
        raise SoundValidationError("The audio file is empty.", code="empty", format_name=format_name)
    if size > MAX_NOTIFICATION_SOUND_SIZE:
        raise SoundValidationError("Maximum notification sound size is 5 MB.", code="size", format_name=format_name)
    data = sound_path.read_bytes()[:8192]
    if not _magic_matches(format_name, data):
        raise SoundValidationError("The file header does not match its extension.", code="magic", format_name=format_name)
    mime = _mime_type(sound_path)
    if mime not in SUPPORTED_NOTIFICATION_SOUND_MIME_TYPES[format_name]:
        raise SoundValidationError("The audio MIME type does not match its extension.", code="mime-mismatch", format_name=format_name)
    duration, _detected = _decode_and_probe(sound_path, format_name)
    if duration > MAX_NOTIFICATION_SOUND_DURATION + _DURATION_PADDING_TOLERANCE:
        raise SoundValidationError("Maximum notification sound duration is 10 seconds.", code="duration", format_name=format_name)
    return NotificationSoundMetadata(sound_path, format_name, mime, duration, size)
