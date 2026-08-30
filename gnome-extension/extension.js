// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright (C) 2026 Vox Sentry contributors

import GObject from 'gi://GObject';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {NotificationManager} from './notificationManager.js';

const BUS = 'io.github.gnome_vox_sentry';
const PATH = '/io/github/gnome_vox_sentry';
const IFACE = 'io.github.gnome_vox_sentry';

function isCancelled(error) {
    return error instanceof GLib.Error && error.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED);
}

const AgentIndicator = GObject.registerClass(class AgentIndicator extends PanelMenu.Button {
    _init(settings, openPreferences) {
        super._init(0.0, 'Vox Sentry');
        this.add_style_class_name('vox-sentry-indicator');
        this._settings = settings;
        this._openPreferencesCallback = openPreferences;
        this._settingsSignal = this._settings.connect('changed', () => {
            if (this._snapshot && !this.menu.isOpen) this._render(this._snapshot);
        });
        this._signalIds = [];
        this._refreshSource = 0;
        this._statusCancellable = null;
        this._refreshCancellable = null;
        this._notificationManager = new NotificationManager(settings);
        this._lamps = {};
        this._trafficLight = new St.BoxLayout({style_class: 'vox-sentry-traffic-light'});
        for (const color of ['red', 'amber', 'green']) {
            const lamp = new St.Label({text: '●', style_class: `vox-sentry-lamp vox-sentry-lamp-${color}`});
            this._trafficLight.add_child(lamp);
            this._lamps[color] = lamp;
        }
        this.add_child(this._trafficLight);
        this._title = new PopupMenu.PopupMenuItem('Vox Sentry');
        this._title.actor.reactive = false;
        this._title.actor.add_style_class_name('vox-sentry-status-item');
        this._title.label.add_style_class_name('vox-sentry-status-label');
        this.menu.addMenuItem(this._title);
        this._statusDetail = new PopupMenu.PopupMenuItem('Connecting to agents…');
        this._statusDetail.actor.reactive = false;
        this._statusDetail.actor.add_style_class_name('vox-sentry-status-detail-item');
        this._statusDetail.label.add_style_class_name('vox-sentry-status-detail');
        this.menu.addMenuItem(this._statusDetail);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._providers = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._providers);
        this._lastProviderStates = null;
        this._refresh = new PopupMenu.PopupMenuItem('Refresh status');
        this._refresh.connect('activate', () => this._refreshNow());
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this.menu.addMenuItem(this._refresh);
        this._settingsItem = new PopupMenu.PopupMenuItem('Settings');
        this._settingsItem.actor.insert_child_at_index(new St.Icon({
            icon_name: 'emblem-system-symbolic',
            icon_size: 16,
            style_class: 'vox-sentry-menu-icon',
        }), 0);
        this._settingsItem.connect('activate', () => this._openPreferences());
        this.menu.addMenuItem(this._settingsItem);
        this._menuSignal = this.menu.connect('open-state-changed', (_menu, open) => {
            if (!open && this._snapshot) this._renderMenu(this._snapshot);
        });
        try {
            this._proxy = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, null, BUS, PATH, IFACE, null);
            this._signalIds.push(this._proxy.connect('g-signal', (_proxy, _sender, signal, parameters) => {
                if (signal === 'StatusChanged') this._load();
                if (signal === 'NotificationTest') this._showTestNotification(parameters.deep_unpack()[0]);
            }));
            // The daemon may start after GNOME Shell has already enabled the
            // extension. Reload when its well-known D-Bus name appears.
            this._signalIds.push(this._proxy.connect('notify::g-name-owner', () => this._load()));
            this._load();
            // Also cover a daemon restart where the proxy does not emit a
            // name-owner notification on older GNOME/GJS versions.
            this._refreshSource = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 5, () => {
                if (!this._proxy) return GLib.SOURCE_REMOVE;
                this._load();
                return GLib.SOURCE_CONTINUE;
            });
        } catch (error) {
            log(`Vox Sentry D-Bus connection failed: ${error.message}`);
            this._render({status: 'OFFLINE', sessions: []});
        }
    }

    _load() {
        if (!this._proxy || this._statusCancellable) return;
        const cancellable = new Gio.Cancellable();
        this._statusCancellable = cancellable;
        this._proxy.call('GetStatus', null, Gio.DBusCallFlags.NONE, 1500, cancellable, (_proxy, result) => {
            if (this._statusCancellable !== cancellable) return;
            this._statusCancellable = null;
            try {
                this._render(JSON.parse(result.deep_unpack()[0]));
            } catch (error) {
                if (isCancelled(error)) return;
                log(`Vox Sentry status request failed: ${error.message}`);
                this._render({status: 'OFFLINE', sessions: []});
            }
        });
    }

    _refreshNow() {
        if (!this._proxy || this._refreshCancellable) return;
        this._refresh.label.text = 'Refreshing…';
        const cancellable = new Gio.Cancellable();
        this._refreshCancellable = cancellable;
        try {
            this._proxy.call('Reload', null, Gio.DBusCallFlags.NONE, 3000, cancellable, (_proxy, result) => {
                if (this._refreshCancellable !== cancellable) return;
                this._refreshCancellable = null;
                if (!this._refresh) return;
                this._refresh.label.text = 'Refresh status';
                try {
                    this._render(JSON.parse(result.deep_unpack()[0]));
                } catch (error) {
                    if (isCancelled(error)) return;
                    log(`Vox Sentry refresh failed: ${error.message}`);
                    this._load();
                }
            });
        } catch (error) {
            this._refreshCancellable = null;
            this._refresh.label.text = 'Refresh status';
            log(`Vox Sentry refresh failed: ${error.message}`);
            this._load();
        }
    }

    _openPreferences() {
        this._openPreferencesCallback();
    }

    _showTestNotification(eventType) {
        const labels = {
            WAITING: 'Waiting',
            COMPLETED: 'Completed',
            ERROR: 'Error',
            RATE_LIMITED: 'Rate limited',
        };
        const label = labels[eventType] || 'Notification';
        this._notificationManager.notify(
            'Vox Sentry · Test',
            `${label} notification test — using the current sound configuration.`,
            eventType);
    }

    _render(snapshot) {
        this._snapshot = snapshot;
        if (!this._trafficLight || !this._title) return;
        const status = snapshot.status || 'UNKNOWN';
        const connectedProviders = this._connectedProviders(snapshot);
        const providerNames = connectedProviders
            .map(provider => provider.name);
        const subject = providerNames.length ? providerNames.join(', ') : 'Agent';
        const presentation = {
            WORKING: {light: 'amber', label: 'Working', detail: `${subject} is processing`},
            THINKING: {light: 'amber', label: 'Thinking', detail: `${subject} is planning`},
            IDLE: {light: 'green', label: 'Ready', detail: `${subject} is idle`},
            COMPLETED: {light: 'green', label: 'Completed', detail: 'The last task finished'},
            WAITING: {light: 'amber', label: 'Waiting', detail: `${subject} needs your input`},
            UNKNOWN: {light: 'amber', label: 'Unknown', detail: 'Waiting for a status update'},
            OFFLINE: {light: 'red', label: 'Offline', detail: 'The local monitor is unavailable'},
            ERROR: {light: 'red', label: 'Error', detail: `${subject} reported an error`},
            RATE_LIMITED: {light: 'red', label: 'Limit reached', detail: `${subject} usage is currently limited`},
        }[status] || {light: 'amber', label: 'Unknown', detail: 'Waiting for a status update'};
        this._setTrafficLight(presentation.light);
        this._title.label.text = `Vox Sentry · ${presentation.label}`;
        this._statusDetail.label.text = presentation.detail;
        this._notifyProviderTransitions(connectedProviders);
        if (this.menu.isOpen) return;
        this._renderMenu(snapshot);
    }

    _setTrafficLight(activeColor) {
        for (const [color, lamp] of Object.entries(this._lamps)) {
            lamp.remove_style_class_name('active');
            lamp.remove_style_class_name(`vox-sentry-lamp-${color}-active`);
            if (color === activeColor) {
                lamp.add_style_class_name('active');
                lamp.add_style_class_name(`vox-sentry-lamp-${color}-active`);
            }
        }
    }

    _connectedProviders(snapshot) {
        return (snapshot.providers || []).filter(provider =>
            provider.active !== false && provider.status && provider.status !== 'OFFLINE');
    }

    _visibleProviders(snapshot) {
        if (this._settings.get_boolean('show-connected-only') !== false)
            return this._connectedProviders(snapshot);
        return snapshot.providers || [];
    }

    _notifyProviderTransitions(providers) {
        const current = Object.fromEntries(providers.map(provider => [provider.id, provider.status]));
        if (this._lastProviderStates === null) {
            this._lastProviderStates = current;
            return;
        }
        const byId = Object.fromEntries(providers.map(provider => [provider.id, provider]));
        for (const [providerId, nextStatus] of Object.entries(current)) {
            const previousStatus = this._lastProviderStates[providerId];
            if (!previousStatus || previousStatus === nextStatus) continue;
            const provider = byId[providerId];
            let message = null;
            let eventType = null;
            if (['WORKING', 'THINKING'].includes(previousStatus) && ['IDLE', 'COMPLETED'].includes(nextStatus)) {
                message = nextStatus === 'COMPLETED' ? 'completed the task.' : 'is ready.';
                eventType = 'COMPLETED';
            } else if (nextStatus === 'RATE_LIMITED' && previousStatus !== 'RATE_LIMITED') {
                message = 'reached its usage limit.';
                eventType = 'RATE_LIMITED';
            } else if (nextStatus === 'WAITING' && previousStatus !== 'WAITING') {
                message = 'is waiting for your input.';
                eventType = 'WAITING';
            } else if (nextStatus === 'ERROR' && previousStatus !== 'ERROR') {
                message = 'reported an error.';
                eventType = 'ERROR';
            }
            if (message) this._notify(message[0].toUpperCase() + message.slice(1), `${provider.name} · Vox Sentry`, eventType);
        }
        this._lastProviderStates = current;
    }

    _providerIcon() {
        return new St.Icon({
            gicon: Gio.ThemedIcon.new('applications-development-symbolic'),
            icon_size: 16,
            style_class: 'vox-sentry-provider-icon',
        });
    }

    _notify(body, title = 'Vox Sentry', eventType = null) {
        this._notificationManager.notify(title, body, eventType);
    }

    _renderMenu(snapshot) {
        if (!this._providers) return;
        this._providers.removeAll();
        const allSessions = snapshot.sessions || [];
        const showMultipleSessions = this._settings.get_boolean('show-multiple-sessions') !== false;
        const showUsage = this._settings.get_boolean('show-usage') !== false;
        const showLimits = this._settings.get_boolean('show-limits') !== false;
        const statusPresentation = {
            WORKING: ['Working', 'amber'], THINKING: ['Thinking', 'amber'], WAITING: ['Waiting', 'amber'],
            IDLE: ['Idle', 'green'], COMPLETED: ['Completed', 'green'], OFFLINE: ['Offline', 'red'],
            ERROR: ['Error', 'red'], RATE_LIMITED: ['Limit reached', 'red'], UNKNOWN: ['Unknown', 'amber'],
        };
        const addLine = (menu, label, value, valueClass = 'info') => {
            const item = new PopupMenu.PopupBaseMenuItem({reactive: false, style_class: 'vox-sentry-usage-item'});
            item.add_child(new St.Label({text: `${label}:`, style_class: 'vox-sentry-usage-label'}));
            const parts = Array.isArray(value) ? value : [{text: value, style_class: valueClass}];
            for (const part of parts) {
                if (part.text) item.add_child(new St.Label({text: part.text, style_class: `vox-sentry-usage-value ${part.style_class || valueClass}`}));
            }
            menu.addMenuItem(item);
        };
        const addUsage = (menu, usage) => {
            if (!showUsage || !usage) return;
            const details = usage.details || {};
            let count = 0;
            const formatTokens = value => value == null ? null : `${(Number(value) / 1000000).toFixed(1)}M tokens`;
            if (details.todayTokens != null) { addLine(menu, 'Today', formatTokens(details.todayTokens), 'tokens'); count++; }
            else if (details.latestDailyTokens != null) {
                const date = details.latestDailyDate ? ` (${details.latestDailyDate})` : '';
                addLine(menu, `Latest day${date}`, formatTokens(details.latestDailyTokens), 'tokens'); count++;
            }
            if (details.lifetimeTokens != null) { addLine(menu, 'Lifetime', formatTokens(details.lifetimeTokens), 'tokens'); count++; }
            if (showLimits) {
                const formatWindow = window => {
                    if (!window) return;
                    const mins = window.windowDurationMins;
                    const duration = mins >= 10080 ? '7d' : mins >= 1440 ? `${Math.round(mins / 1440)}d` : `${Math.round(mins / 60)}h`;
                    const percent = Number(window.usedPercent);
                    const level = Number.isFinite(percent) && percent >= 90 ? 'critical' : Number.isFinite(percent) && percent >= 70 ? 'warning' : 'healthy';
                    const reset = window.resetsAt ? ` · reset ${new Date(window.resetsAt * 1000).toLocaleTimeString()}` : '';
                    addLine(menu, duration, [{text: `${window.usedPercent}% used`, style_class: level}, {text: reset, style_class: 'reset'}]);
                    count++;
                };
                formatWindow(details.primary); formatWindow(details.secondary);
            }
            if (!count) addLine(menu, 'Consumption', 'Unavailable', 'reset');
        };
        const providers = this._visibleProviders(snapshot);
        for (const provider of providers) {
            const state = statusPresentation[provider.status] ? provider.status : 'UNKNOWN';
            const [label, color] = statusPresentation[state];
            const submenu = new PopupMenu.PopupSubMenuMenuItem(`${provider.name} · ${label}`, false);
            submenu.actor.add_style_class_name('vox-sentry-provider-item');
            submenu.actor.insert_child_at_index(this._providerIcon(), 0);
            submenu.menu.actor.add_style_class_name('vox-sentry-provider-menu');
            submenu.label.add_style_class_name('vox-sentry-provider-label');
            submenu.label.add_style_class_name(`vox-sentry-provider-status-${color}`);
            const providerSessions = allSessions
                .filter(session => session.provider === provider.id)
                .slice(0, showMultipleSessions ? undefined : 1);
            if (providerSessions.length) {
                for (const session of providerSessions) {
                    const item = new PopupMenu.PopupMenuItem(`${session.projectName || 'Workspace'} · ${session.status.toLowerCase()}`);
                    item.actor.reactive = false;
                    submenu.menu.addMenuItem(item);
                }
            } else {
                const item = new PopupMenu.PopupMenuItem('No active sessions');
                item.actor.reactive = false;
                submenu.menu.addMenuItem(item);
            }
            submenu.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
            const usage = snapshot.usage || {};
            addUsage(submenu.menu, usage[provider.id]);
            if (!usage[provider.id]) addLine(submenu.menu, 'Consumption', 'Unavailable', 'reset');
            this._providers.addMenuItem(submenu);
        }
        if (!providers.length) {
            const emptyLabel = this._settings.get_boolean('show-connected-only') !== false
                ? 'No connected providers'
                : 'No providers detected';
            const item = new PopupMenu.PopupMenuItem(emptyLabel);
            item.actor.reactive = false;
            this._providers.addMenuItem(item);
        }
    }

    _cleanup() {
        if (this._refreshSource) {
            GLib.Source.remove(this._refreshSource);
            this._refreshSource = 0;
        }
        if (this._statusCancellable) this._statusCancellable.cancel();
        this._statusCancellable = null;
        if (this._refreshCancellable) this._refreshCancellable.cancel();
        this._refreshCancellable = null;
        if (this._proxy) {
            for (const signalId of this._signalIds) this._proxy.disconnect(signalId);
            this._signalIds = [];
            this._proxy = null;
        }
        if (this._menuSignal) {
            this.menu.disconnect(this._menuSignal);
            this._menuSignal = 0;
        }
        if (this._settingsSignal) {
            this._settings.disconnect(this._settingsSignal);
            this._settingsSignal = 0;
        }
        this._notificationManager.destroy();
        this._notificationManager = null;
        this._settings = null;
        this._openPreferencesCallback = null;
        this._trafficLight = null;
        this._title = null;
        this._statusDetail = null;
        this._providers = null;
        this._refresh = null;
    }

    destroy() {
        this._cleanup();
        super.destroy();
    }

});

export default class VoxSentryExtension extends Extension {
    enable() {
        this._indicator = new AgentIndicator(this.getSettings(), () => this.openPreferences());
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        if (this._indicator) this._indicator.destroy();
        this._indicator = null;
    }
}
