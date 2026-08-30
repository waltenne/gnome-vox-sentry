// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright (C) 2026 Vox Sentry contributors

import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';
import {MP3_DECODER_ERROR, SoundManager} from './soundManager.js';

export class NotificationManager {
    constructor(settings) {
        this._settings = settings;
        this._soundManager = new SoundManager(settings);
    }

    _enabled() {
        return this._settings.get_boolean('notifications-enabled');
    }

    _soundsEnabled() {
        return this._settings.get_boolean('sounds-enabled');
    }

    notify(title, body, eventType = null) {
        if (!this._enabled()) return;
        this._show(title, body);
        if (!eventType || !this._soundsEnabled()) return;
        try {
            this._soundManager.playForEvent(eventType);
        } catch (error) {
            if (error.code === 'decoder-unavailable' && error.format === 'mp3') {
                this._show(MP3_DECODER_ERROR.title, MP3_DECODER_ERROR.body);
            } else {
                log(`Vox Sentry sound notification failed: ${error.message}`);
            }
        }
    }

    _show(title, body) {
        try {
            const source = MessageTray.getSystemSource();
            source.addNotification(new MessageTray.Notification({
                source,
                title,
                body,
                isTransient: false,
            }));
        } catch (error) {
            log(`Vox Sentry notification failed: ${error.message}`);
        }
    }

    preview(path) {
        return this._soundManager.preview(path);
    }

    destroy() {
        this._soundManager.destroy();
        this._soundManager = null;
        this._settings = null;
    }
}
