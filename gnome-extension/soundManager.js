// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright (C) 2026 Vox Sentry contributors

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Gst from 'gi://Gst';
import GstPbutils from 'gi://GstPbutils';

export const MAX_NOTIFICATION_SOUND_DURATION = 10;
export const MAX_NOTIFICATION_SOUND_SIZE = 5 * 1024 * 1024;
const DURATION_PADDING_TOLERANCE = 0.05;
export const SUPPORTED_NOTIFICATION_SOUND_FORMATS = ['mp3', 'ogg', 'oga', 'wav', 'flac'];
export const SUPPORTED_NOTIFICATION_SOUND_MIME_TYPES = {
    mp3: ['audio/mpeg', 'audio/mp3', 'audio/x-mpeg'],
    ogg: ['audio/ogg', 'application/ogg', 'audio/x-ogg', 'audio/x-vorbis+ogg', 'audio/x-opus+ogg'],
    oga: ['audio/ogg', 'application/ogg', 'audio/x-ogg', 'audio/x-vorbis+ogg', 'audio/x-opus+ogg'],
    wav: ['audio/wav', 'audio/x-wav', 'audio/vnd.wave', 'audio/wave'],
    flac: ['audio/flac', 'audio/x-flac'],
};

export const MP3_DECODER_ERROR = {
    title: 'Unable to play MP3 file',
    body: 'Vox Sentry could not decode the selected MP3 audio.\n\nVerify that the required multimedia codecs are available on your system.',
};

class SoundValidationError extends Error {
    constructor(message, code, format) {
        super(message);
        this.name = 'SoundValidationError';
        this.code = code;
        this.format = format;
    }
}

function formatForPath(path) {
    const suffix = Gio.File.new_for_path(path).get_basename().split('.').pop().toLowerCase();
    if (!SUPPORTED_NOTIFICATION_SOUND_FORMATS.includes(suffix))
        throw new SoundValidationError('Supported formats: MP3, OGG, OGA, WAV and FLAC', 'unsupported-format', suffix);
    return suffix;
}

function startsWith(data, text) {
    return [...text].every((value, index) => data[index] === value.charCodeAt(0));
}

function mp3FrameLength(data, index) {
    if (index + 4 > data.length) return null;
    const header = (data[index] << 24) | (data[index + 1] << 16) | (data[index + 2] << 8) | data[index + 3];
    if ((header >>> 21) !== 0x7ff) return null;
    const version = (header >>> 19) & 0x3;
    const layer = (header >>> 17) & 0x3;
    const bitrateIndex = (header >>> 12) & 0xf;
    const sampleRateIndex = (header >>> 10) & 0x3;
    if (version === 1 || layer === 0 || bitrateIndex === 0 || bitrateIndex === 15 || sampleRateIndex === 3) return null;
    const rates = {
        '3:3': [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 0],
        '3:2': [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0],
        '3:1': [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
        '2:3': [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0],
        '2:2': [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
        '2:1': [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
        '0:3': [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0],
        '0:2': [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
        '0:1': [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
    };
    const sampleRates = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]};
    const bitrate = rates[`${version}:${layer}`][bitrateIndex] * 1000;
    const sampleRate = sampleRates[version][sampleRateIndex];
    const padding = (header >>> 9) & 1;
    if (layer === 3) return Math.floor(12 * bitrate / sampleRate + padding) * 4;
    return Math.floor((version === 3 ? 144 : 72) * bitrate / sampleRate) + padding;
}

function hasMp3Frame(data) {
    if (startsWith(data, 'ID3')) return true;
    for (let index = 0; index + 3 < Math.min(data.length, 8192); index++) {
        const length = mp3FrameLength(data, index);
        if (length && mp3FrameLength(data, index + length)) return true;
    }
    return false;
}

function matchesMagic(format, data) {
    if (format === 'mp3') return hasMp3Frame(data);
    if (format === 'ogg' || format === 'oga') return startsWith(data, 'OggS');
    if (format === 'wav') return startsWith(data, 'RIFF') && startsWith(data.slice(8), 'WAVE');
    if (format === 'flac') return startsWith(data, 'fLaC');
    return false;
}

function getMimeType(path, data) {
    const [contentType] = Gio.content_type_guess(path, data);
    const mime = Gio.content_type_get_mime_type(contentType);
    return mime ? mime.toLowerCase() : '';
}

function decoderError(format, message = 'Required multimedia decoder is not available.') {
    return new SoundValidationError(message, 'decoder-unavailable', format);
}

export function validateSoundFile(path) {
    const file = Gio.File.new_for_path(path);
    const format = formatForPath(path);
    let info;
    try {
        info = file.query_info('standard::size', Gio.FileQueryInfoFlags.NONE, null);
    } catch (_) {
        throw new SoundValidationError('The selected audio file does not exist.', 'missing', format);
    }
    const size = Number(info.get_size());
    if (size <= 0) throw new SoundValidationError('The audio file is empty.', 'empty', format);
    if (size > MAX_NOTIFICATION_SOUND_SIZE) throw new SoundValidationError('Maximum notification sound size is 5 MB.', 'size', format);
    const [, contents] = GLib.file_get_contents(path);
    const data = Array.from(contents || []);
    if (!matchesMagic(format, data)) throw new SoundValidationError('The file header does not match its extension.', 'magic', format);
    const mime = getMimeType(path, contents);
    if (!SUPPORTED_NOTIFICATION_SOUND_MIME_TYPES[format].includes(mime))
        throw new SoundValidationError('The audio MIME type does not match its extension.', 'mime-mismatch', format);

    let discoverer;
    try {
        discoverer = GstPbutils.Discoverer.new(3n * 1000000000n);
        const discoverInfo = discoverer.discover_uri(file.get_uri());
        const missing = discoverInfo.get_missing_elements_installer_details();
        if (missing && missing.length) throw decoderError(format);
        const duration = Number(discoverInfo.get_duration()) / 1e9;
        if (!Number.isFinite(duration) || duration <= 0)
            throw new SoundValidationError('The audio file is corrupt or cannot be decoded.', 'decode', format);
        if (duration > MAX_NOTIFICATION_SOUND_DURATION + DURATION_PADDING_TOLERANCE)
            throw new SoundValidationError('Maximum notification sound duration is 10 seconds.', 'duration', format);
        _verifyDecoder(file.get_uri(), format);
        return {path, format, mime, duration, size};
    } catch (error) {
        if (error instanceof SoundValidationError) throw error;
        const message = String(error.message || error);
        if (format === 'mp3' && /decoder|codec|plugin|missing|not found/i.test(message)) throw decoderError(format);
        throw new SoundValidationError('The audio file is corrupt or cannot be decoded.', 'decode', format);
    }
}

function _verifyDecoder(uri, format) {
    const pipeline = Gst.ElementFactory.make('playbin', 'vox-sentry-validator');
    if (!pipeline) throw decoderError(format);
    pipeline.set_property('uri', uri);
    pipeline.set_property('audio-sink', Gst.ElementFactory.make('fakesink', 'vox-sentry-audio-validator'));
    const result = pipeline.set_state(Gst.State.PAUSED);
    if (result === Gst.StateChangeReturn.FAILURE) {
        pipeline.set_state(Gst.State.NULL);
        throw decoderError(format);
    }
    const message = pipeline.get_bus().timed_pop_filtered(
        3n * 1000000000n,
        Gst.MessageType.ERROR | Gst.MessageType.ASYNC_DONE);
    pipeline.set_state(Gst.State.NULL);
    if (!message || message.type === Gst.MessageType.ERROR) throw decoderError(format);
}

function defaultSoundCandidates(eventType) {
    const names = {
        WAITING: [
            'string.ogg',
            'message-new-instant.oga',
            'message-new-instant.ogg',
            'dialog-warning.oga',
            'dialog-warning.ogg',
        ],
        COMPLETED: [
            'click.ogg',
            'complete.oga',
            'complete.ogg',
        ],
        ERROR: [
            'swing.ogg',
            'dialog-error.oga',
            'dialog-error.ogg',
            'suspend-error.oga',
            'suspend-error.ogg',
            'dialog-information.oga',
            'dialog-information.ogg',
        ],
        RATE_LIMITED: [
            'hum.ogg',
            'alarm-clock-elapsed.oga',
            'alarm-clock-elapsed.ogg',
            'bell.oga',
            'bell.ogg',
            'dialog-warning.oga',
            'dialog-warning.ogg',
        ],
    }[eventType] || ['dialog-information.oga', 'dialog-information.ogg'];
    const dirs = [GLib.get_user_data_dir(), ...GLib.get_system_data_dirs()];
    for (const dir of dirs) {
        for (const name of names) {
            for (const theme of ['freedesktop/stereo', 'gnome/default/alerts', 'zorin/stereo']) {
                const path = GLib.build_filenamev([dir, 'sounds', theme, name]);
                if (Gio.File.new_for_path(path).query_exists(null)) return path;
            }
        }
    }
    return null;
}

export class SoundManager {
    constructor(settings) {
        Gst.init(null);
        this._settings = settings;
        this._pipeline = null;
    }

    _configuredPath(eventType) {
        const key = {
            WAITING: 'sound-waiting',
            COMPLETED: 'sound-completed',
            ERROR: 'sound-error',
            RATE_LIMITED: 'sound-rate-limited',
        }[eventType];
        return key ? this._settings.get_string(key) || '' : '';
    }

    _pathForEvent(eventType) {
        const custom = this._configuredPath(eventType);
        if (!custom) return defaultSoundCandidates(eventType);
        try {
            validateSoundFile(custom);
            return custom;
        } catch (error) {
            // A removed or corrupted custom file must never disable event
            // notifications; use the system sound unless the MP3 decoder is
            // unavailable, which deserves the explicit diagnostic below.
            if (error.code === 'decoder-unavailable' && error.format === 'mp3') throw error;
            log(`Vox Sentry custom sound invalid; using system fallback: ${error.message}`);
            return defaultSoundCandidates(eventType);
        }
    }

    playForEvent(eventType) {
        if (this._settings.get_boolean('sounds-enabled') === false) return;
        const path = this._pathForEvent(eventType);
        if (!path) return;
        try {
            validateSoundFile(path);
            this.play(path);
        } catch (error) {
            if (error.code === 'decoder-unavailable' && error.format === 'mp3') throw error;
            log(`Vox Sentry sound skipped: ${error.message}`);
        }
    }

    preview(path) {
        validateSoundFile(path);
        this.play(path);
    }

    play(path) {
        this.stop();
        const pipeline = Gst.ElementFactory.make('playbin', 'vox-sentry-sound');
        if (!pipeline) throw decoderError(formatForPath(path));
        pipeline.set_property('uri', Gio.File.new_for_path(path).get_uri());
        const bus = pipeline.get_bus();
        bus.add_signal_watch();
        bus.connect('message', (_bus, message) => {
            if (message.type === Gst.MessageType.EOS || message.type === Gst.MessageType.ERROR) this.stop();
        });
        this._pipeline = pipeline;
        const result = pipeline.set_state(Gst.State.PLAYING);
        if (result === Gst.StateChangeReturn.FAILURE) {
            this.stop();
            throw decoderError(formatForPath(path));
        }
    }

    stop() {
        if (!this._pipeline) return;
        this._pipeline.set_state(Gst.State.NULL);
        this._pipeline.get_bus().remove_signal_watch();
        this._pipeline = null;
    }

    destroy() {
        this.stop();
    }
}
