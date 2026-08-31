// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright (C) 2026 Vox Sentry contributors

// Normalized domain states and visual presentation are kept together here.
// Providers and Core continue using the normalized status names unchanged.
export const STATUS_ORDER = [
    'OFFLINE', 'IDLE', 'THINKING', 'WORKING', 'WAITING',
    'COMPLETED', 'ERROR', 'RATE_LIMITED', 'UNKNOWN',
];

export const STATUS_PRESENTATION = Object.freeze({
    OFFLINE: {statusClass: 'offline', label: 'Offline', indicatorLabel: 'Offline', colorName: 'gray', color: '#7a7a7a'},
    IDLE: {statusClass: 'idle', label: 'Idle', indicatorLabel: 'Ready', colorName: 'green', color: '#2fb344'},
    THINKING: {statusClass: 'thinking', label: 'Thinking', indicatorLabel: 'Thinking', colorName: 'purple', color: '#a855f7'},
    WORKING: {statusClass: 'working', label: 'Working', indicatorLabel: 'Working', colorName: 'blue', color: '#3b82f6'},
    WAITING: {statusClass: 'waiting', label: 'Waiting', indicatorLabel: 'Waiting', colorName: 'yellow', color: '#facc15'},
    COMPLETED: {statusClass: 'completed', label: 'Completed', indicatorLabel: 'Completed', colorName: 'bright green', color: '#22c55e'},
    ERROR: {statusClass: 'error', label: 'Error', indicatorLabel: 'Error', colorName: 'red', color: '#ef4444'},
    RATE_LIMITED: {statusClass: 'rate-limited', label: 'Limit reached', indicatorLabel: 'Limit reached', colorName: 'orange', color: '#f97316'},
    UNKNOWN: {statusClass: 'unknown', label: 'Unknown', indicatorLabel: 'Unknown', colorName: 'blue-gray', color: '#94a3b8'},
});

export function presentationFor(status) {
    return STATUS_PRESENTATION[status] || STATUS_PRESENTATION.UNKNOWN;
}

export function statusClassFor(status) {
    return `vox-sentry-status-${presentationFor(status).statusClass}`;
}
