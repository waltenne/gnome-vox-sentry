// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright (C) 2026 Vox Sentry contributors

import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Gtk from 'gi://Gtk';
import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';
import {
    MAX_NOTIFICATION_SOUND_DURATION,
    MAX_NOTIFICATION_SOUND_SIZE,
    MP3_DECODER_ERROR,
    SoundManager,
    SUPPORTED_NOTIFICATION_SOUND_FORMATS,
    SUPPORTED_NOTIFICATION_SOUND_MIME_TYPES,
    validateSoundFile,
} from './soundManager.js';
import {STATUS_ORDER, presentationFor} from './statusPresentation.js';

const BUS = 'io.github.gnome_vox_sentry';
const PATH = '/io/github/gnome_vox_sentry';
const IFACE = 'io.github.gnome_vox_sentry';

function isCancelled(error) {
    return error instanceof GLib.Error && error.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED);
}

const PROVIDERS = [
    ['codex', 'Codex'],
    ['gemini', 'Gemini'],
    ['antigravity', 'Antigravity'],
    ['copilot', 'Copilot'],
    ['claude', 'Claude'],
    ['opencode', 'OpenCode'],
];

const TEST_EVENTS = [
    ['WAITING', 'Waiting'],
    ['COMPLETED', 'Completed'],
    ['ERROR', 'Error'],
    ['RATE_LIMITED', 'Rate limited'],
];

const STATUS_TESTS = STATUS_ORDER.map(status => {
    const presentation = presentationFor(status);
    return [status, presentation.label, presentation.colorName, presentation.color];
});

export default class VoxSentryPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        this._settings = this.getSettings();
        this._providerRows = new Map();
        this._soundRows = new Map();
        this._window = window;
        this._soundManager = new SoundManager(this._settings);
        this._proxy = null;
        this._statusSource = 0;

        window.set_title('Vox Sentry Settings');
        window.set_default_size(920, 700);
        window.set_search_enabled(true);
        this._addPage(window, this._behaviorPage(), 'general', 'General', 'preferences-system-symbolic');
        this._addPage(window, this._providersPage(), 'providers', 'Providers', 'applications-system-symbolic');
        this._addPage(window, this._notificationsPage(), 'notifications', 'Notifications', 'preferences-desktop-notification-symbolic');
        this._addPage(window, this._soundsPage(), 'sounds', 'Sounds', 'audio-x-generic-symbolic');
        this._addPage(window, this._aboutPage(), 'about', 'About', 'help-about-symbolic');

        try {
            this._proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                null,
                BUS,
                PATH,
                IFACE,
                null);
        } catch (error) {
            this._proxy = null;
            log(`Vox Sentry preferences D-Bus connection failed: ${error.message}`);
        }
        this._loadProviderStatus();
        this._statusSource = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            Math.max(2, this._settings.get_int('refresh-interval')),
            () => {
                if (!this._window) return GLib.SOURCE_REMOVE;
                this._loadProviderStatus();
                return GLib.SOURCE_CONTINUE;
            });
        window.connect('close-request', () => {
            if (this._statusSource) {
                GLib.Source.remove(this._statusSource);
                this._statusSource = 0;
            }
            this._soundManager.destroy();
            this._soundManager = null;
            this._proxy = null;
            this._providerRows.clear();
            this._soundRows.clear();
            this._settings = null;
            this._window = null;
            return false;
        });
    }

    _addPage(window, page, name, title, iconName) {
        page.set_name(name);
        page.set_title(title);
        page.set_icon_name(iconName);
        window.add(page);
    }

    _behaviorPage() {
        const page = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({
            title: 'General behavior',
            description: 'Control which agents appear in the indicator and how activity is presented.',
        });
        const mode = new Adw.ComboRow({
            title: 'Provider mode',
            subtitle: 'Choose how providers are enabled by the daemon.',
            model: Gtk.StringList.new(['Auto', 'Manual', 'Multi']),
        });
        mode.selected = Math.max(0, ['auto', 'manual', 'multi'].indexOf(this._settings.get_string('provider-mode')));
        mode.connect('notify::selected', () => this._settings.set_string('provider-mode', ['auto', 'manual', 'multi'][mode.selected]));
        group.add(mode);
        this._addSwitch(group, 'show-connected-only', 'Show only connected providers', 'Hide providers that are not currently connected from the dropdown.');
        this._addSwitch(group, 'show-multiple-sessions', 'Show multiple sessions', 'Show every live workspace session under each provider.');
        this._addSwitch(group, 'notifications-enabled', 'Desktop notifications', 'Notify when a provider finishes, needs input, fails or reaches a quota limit.');
        page.add(group);

        const colors = new Adw.PreferencesGroup({
            title: 'Status color test',
            description: 'Preview each indicator color and optionally show it in the panel for five seconds.',
        });
        const statusRow = new Adw.ActionRow({
            title: 'Status to test',
            subtitle: 'Choose a state to preview.',
        });
        const status = new Gtk.DropDown({
            model: Gtk.StringList.new(STATUS_TESTS.map(([, label]) => label)),
        });
        status.set_size_request(180, -1);
        status.set_factory(this._statusOptionFactory());
        status.set_list_factory(this._statusOptionFactory());
        statusRow.add_suffix(status);
        const previewRow = new Adw.ActionRow({title: 'Preview', subtitle: 'The selected status color is shown here.'});
        const dot = new Gtk.Label({label: '●', valign: Gtk.Align.CENTER});
        dot.add_css_class('vox-sentry-status-preview-dot');
        previewRow.add_prefix(dot);
        colors.add(statusRow);
        colors.add(previewRow);

        const panelRow = new Adw.ActionRow({
            title: 'Test indicator color',
            subtitle: 'Temporarily changes the status dot in the GNOME panel.',
        });
        const panelButton = new Gtk.Button({label: 'Test', valign: Gtk.Align.CENTER});
        panelButton.add_css_class('suggested-action');
        panelButton.connect('clicked', () => this._sendStatusTest(STATUS_TESTS[status.selected][0]));
        panelRow.add_suffix(panelButton);
        colors.add(panelRow);
        status.connect('notify::selected', () => this._updateStatusPreview(status, dot, previewRow));
        this._updateStatusPreview(status, dot, previewRow);
        page.add(colors);

        const usage = new Adw.PreferencesGroup({
            title: 'Usage and limits',
            description: 'Choose which consumption details appear when a provider exposes them.',
        });
        this._addSwitch(usage, 'show-usage', 'Show token usage', 'Show aggregate token totals in the provider dropdown.');
        this._addSwitch(usage, 'show-limits', 'Show limits and reset times', 'Show quota windows and their reset times.');
        page.add(usage);

        const monitoring = new Adw.PreferencesGroup({
            title: 'Monitoring',
            description: 'Control how often the daemon checks provider state in the background.',
        });
        const interval = new Adw.SpinRow({
            title: 'Refresh interval',
            subtitle: 'Seconds between automatic provider checks.',
            adjustment: new Gtk.Adjustment({lower: 1, upper: 60, step_increment: 1, value: this._settings.get_int('refresh-interval')}),
        });
        interval.connect('notify::value', () => this._settings.set_int('refresh-interval', interval.value));
        monitoring.add(interval);
        page.add(monitoring);
        return page;
    }

    _updateStatusPreview(status, dot, row) {
        const [, label, color, hex] = STATUS_TESTS[status.selected] || STATUS_TESTS[0];
        dot.set_markup(`<span foreground="${hex}">●</span>`);
        row.title = label;
        row.subtitle = `${label} · ${color} indicator light`;
    }

    _statusOptionFactory() {
        const factory = new Gtk.SignalListItemFactory();
        factory.connect('setup', (_factory, item) => {
            item.set_child(new Gtk.Label({halign: Gtk.Align.START}));
        });
        factory.connect('bind', (_factory, item) => {
            const option = STATUS_TESTS[item.get_position()] || STATUS_TESTS[0];
            const [, label, , hex] = option;
            item.get_child().set_markup(`<span foreground="${hex}">●  ${label}</span>`);
        });
        return factory;
    }

    _sendStatusTest(status) {
        if (!this._proxy) {
            this._showTestError(new Error('The Vox Sentry daemon is not available.'));
            return;
        }
        try {
            this._proxy.call_sync(
                'TestStatus',
                new GLib.Variant('(s)', [status]),
                Gio.DBusCallFlags.NONE,
                3000,
                null);
        } catch (error) {
            this._showTestError(error);
        }
    }

    _providersPage() {
        this._providerPage = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({
            title: 'Provider status',
            description: 'All supported providers are listed here. Status is read locally from the Vox Sentry daemon.',
        });
        const refreshRow = new Adw.ActionRow({
            title: 'Refresh provider status',
            subtitle: 'Ask the daemon for a fresh detection now.',
        });
        const refreshButton = new Gtk.Button({icon_name: 'view-refresh-symbolic', valign: Gtk.Align.CENTER, tooltip_text: 'Refresh now'});
        refreshButton.add_css_class('flat');
        refreshButton.connect('clicked', () => this._loadProviderStatus(true));
        refreshRow.add_suffix(refreshButton);
        group.add(refreshRow);

        for (const [id, name] of PROVIDERS) {
            const row = new Adw.ActionRow({title: name, subtitle: 'Checking status…'});
            row.set_activatable(false);
            row.add_prefix(this._providerIcon());
            const status = new Gtk.Label({label: '…', valign: Gtk.Align.CENTER});
            status.add_css_class('dim-label');
            row.add_suffix(status);
            group.add(row);
            this._providerRows.set(id, {row, status});
        }
        this._providerPage.add(group);
        return this._providerPage;
    }

    _notificationsPage() {
        const page = new Adw.PreferencesPage();
        const behavior = new Adw.PreferencesGroup({
            title: 'Notifications',
            description: 'Choose whether Vox Sentry announces provider state changes visually and audibly.',
        });
        this._addSwitch(behavior, 'sounds-enabled', 'Notification sounds', 'Play a sound for waiting, completed, error and rate-limit events.');
        page.add(behavior);

        const test = new Adw.PreferencesGroup({
            title: 'Test notifications',
            description: 'Send a real GNOME notification using the selected event and its current sound configuration.',
        });
        const event = new Adw.ComboRow({
            title: 'Test event',
            subtitle: 'Choose which event sound should be tested.',
            model: Gtk.StringList.new(TEST_EVENTS.map(([, label]) => label)),
        });
        event.selected = 1;
        const sendRow = new Adw.ActionRow({
            title: 'Send test notification',
            subtitle: 'Uses the notification and sound switches above.',
        });
        const send = new Gtk.Button({label: 'Test', valign: Gtk.Align.CENTER});
        send.add_css_class('suggested-action');
        send.connect('clicked', () => this._sendTestNotification(TEST_EVENTS[event.selected][0]));
        sendRow.add_suffix(send);
        test.add(event);
        test.add(sendRow);
        page.add(test);

        return page;
    }

    _soundsPage() {
        const page = new Adw.PreferencesPage();
        const sounds = new Adw.PreferencesGroup({
            title: 'Custom event sounds',
            description: 'Select a validated local file for an event. Empty selections use the system sound.',
        });
        for (const [key, title] of [
            ['sound-waiting', 'Waiting'],
            ['sound-completed', 'Completed'],
            ['sound-error', 'Error'],
            ['sound-rate-limited', 'Rate limited'],
        ]) sounds.add(this._soundRow(key, title));
        page.add(sounds);

        const requirements = new Adw.PreferencesGroup({title: 'Audio file requirements'});
        requirements.add(new Adw.ActionRow({title: 'Supported formats', subtitle: 'MP3, OGG, OGA, WAV and FLAC'}));
        requirements.add(new Adw.ActionRow({title: 'Maximum duration', subtitle: `${MAX_NOTIFICATION_SOUND_DURATION} seconds` }));
        requirements.add(new Adw.ActionRow({title: 'Maximum size', subtitle: `${MAX_NOTIFICATION_SOUND_SIZE / (1024 * 1024)} MB` }));
        page.add(requirements);
        return page;
    }

    _aboutPage() {
        const page = new Adw.PreferencesPage();
        const about = new Adw.PreferencesGroup({
            title: 'Vox Sentry',
            description: 'A local-first GNOME monitor for coding-agent activity.',
        });
        about.add(new Adw.ActionRow({title: 'Version', subtitle: '0.1.0'}));
        about.add(new Adw.ActionRow({title: 'GNOME Shell', subtitle: '46'}));
        about.add(new Adw.ActionRow({title: 'Privacy', subtitle: 'All provider discovery and status processing stay on this machine.'}));
        const repository = new Adw.ActionRow({title: 'Repository', subtitle: 'Source code, issues and contributions'});
        const link = new Gtk.LinkButton({uri: 'https://github.com/waltenne/gnome-vox-sentry', label: 'Open'});
        repository.add_suffix(link);
        about.add(repository);
        page.add(about);

        const license = new Adw.PreferencesGroup({title: 'License'});
        license.add(new Adw.ActionRow({title: 'GNU GPL-2.0-or-later', subtitle: 'Compatible with GNOME Shell extension distribution.'}));
        page.add(license);
        return page;
    }

    _sendTestNotification(eventType) {
        if (!this._proxy) {
            this._showTestError(new Error('The Vox Sentry daemon is not available.'));
            return;
        }
        try {
            this._proxy.call_sync(
                'TestNotification',
                new GLib.Variant('(s)', [eventType]),
                Gio.DBusCallFlags.NONE,
                3000,
                null);
        } catch (error) {
            this._showTestError(error);
        }
    }

    _showTestError(error) {
        const dialog = new Adw.AlertDialog({
            heading: 'Test notification failed',
            body: error.message,
        });
        dialog.add_response('close', 'Close');
        dialog.set_default_response('close');
        dialog.present(this._window);
    }

    _soundRow(key, title) {
        const row = new Adw.ActionRow({title});
        const preview = new Gtk.Button({icon_name: 'media-playback-start-symbolic', valign: Gtk.Align.CENTER, tooltip_text: 'Preview sound'});
        const choose = new Gtk.Button({icon_name: 'document-open-symbolic', valign: Gtk.Align.CENTER, tooltip_text: 'Choose audio file'});
        const clear = new Gtk.Button({icon_name: 'edit-clear-symbolic', valign: Gtk.Align.CENTER, tooltip_text: 'Use system sound'});
        preview.add_css_class('flat');
        choose.add_css_class('flat');
        clear.add_css_class('flat');
        choose.connect('clicked', () => this._chooseSound(key, row));
        preview.connect('clicked', () => this._previewSound(key));
        clear.connect('clicked', () => {
            this._settings.set_string(key, '');
            this._updateSoundRow(key, row, preview, clear);
        });
        row.add_suffix(preview);
        row.add_suffix(choose);
        row.add_suffix(clear);
        this._soundRows.set(key, {row, preview, clear});
        this._updateSoundRow(key, row, preview, clear);
        return row;
    }

    _updateSoundRow(key, row, preview, clear) {
        const path = this._settings.get_string(key);
        row.subtitle = path ? Gio.File.new_for_path(path).get_basename() : 'System default';
        preview.sensitive = Boolean(path);
        clear.sensitive = Boolean(path);
    }

    _soundFilter() {
        const filter = new Gtk.FileFilter({name: 'Audio files (MP3, OGG, OGA, WAV, FLAC)'});
        for (const format of SUPPORTED_NOTIFICATION_SOUND_FORMATS) filter.add_pattern(`*.${format}`);
        for (const mimes of Object.values(SUPPORTED_NOTIFICATION_SOUND_MIME_TYPES))
            for (const mime of mimes) filter.add_mime_type(mime);
        return filter;
    }

    _chooseSound(key, row) {
        const dialog = new Gtk.FileDialog({title: 'Choose notification sound'});
        const filters = new Gio.ListStore({item_type: Gtk.FileFilter});
        filters.append(this._soundFilter());
        dialog.set_filters(filters);
        dialog.open(this._window, null, (_dialog, result) => {
            try {
                const file = dialog.open_finish(result);
                if (!this._window) return;
                const path = file.get_path();
                validateSoundFile(path);
                this._settings.set_string(key, path);
                const controls = this._soundRows.get(key);
                this._updateSoundRow(key, row, controls.preview, controls.clear);
            } catch (error) {
                if (isCancelled(error)) return;
                this._showSoundError(error);
            }
        });
    }

    _previewSound(key) {
        const path = this._settings.get_string(key);
        if (!path) return;
        try {
            this._soundManager.preview(path);
        } catch (error) {
            this._showSoundError(error);
        }
    }

    _showSoundError(error) {
        const mp3DecoderError = error.code === 'decoder-unavailable' && error.format === 'mp3';
        const dialog = new Adw.AlertDialog({
            heading: mp3DecoderError ? MP3_DECODER_ERROR.title : 'Invalid notification sound',
            body: mp3DecoderError ? MP3_DECODER_ERROR.body : error.message,
        });
        dialog.add_response('close', 'Close');
        dialog.set_default_response('close');
        dialog.present(this._window);
    }

    _addSwitch(group, key, title, subtitle) {
        const row = new Adw.SwitchRow({title, subtitle, active: this._settings.get_boolean(key)});
        row.connect('notify::active', () => this._settings.set_boolean(key, row.active));
        group.add(row);
    }

    _providerIcon() {
        return new Gtk.Image({icon_name: 'applications-development-symbolic', pixel_size: 20});
    }

    _loadProviderStatus(force = false) {
        if (!this._window || !this._proxy) {
            this._setUnavailable();
            return;
        }
        try {
            const method = force ? 'Reload' : 'GetStatus';
            const result = this._proxy.call_sync(method, null, Gio.DBusCallFlags.NONE, 3000, null);
            const snapshot = JSON.parse(result.deep_unpack()[0]);
            this._updateProviderStatus(snapshot);
        } catch (error) {
            log(`Vox Sentry preferences status request failed: ${error.message}`);
            this._setUnavailable();
        }
    }

    _updateProviderStatus(snapshot) {
        const providers = Object.fromEntries((snapshot.providers || []).map(provider => [provider.id, provider]));
        for (const [id, elements] of this._providerRows) {
            const provider = providers[id];
            const state = provider ? provider.status || 'OFFLINE' : 'OFFLINE';
            const presentation = presentationFor(state);
            elements.status.set_markup(`<span foreground="${presentation.color}">● ${presentation.label}</span>`);
            const connection = state === 'OFFLINE' ? 'Not connected' : 'Connected';
            const version = provider && provider.version ? ` · ${provider.version}` : '';
            elements.row.subtitle = `${connection}${version}`;
        }
    }

    _setUnavailable() {
        for (const [, elements] of this._providerRows) {
            const presentation = presentationFor('OFFLINE');
            elements.status.set_markup(`<span foreground="${presentation.color}">● Unavailable</span>`);
            elements.row.subtitle = 'Daemon is not available';
        }
    }
}
