/** Shared display pieces. Markup only — no state, no fetching. */

import { html, raw, icon, escapeHtml } from '../lib/dom.js';
import { pct } from '../lib/format.js';

const R = 44;
const CIRCUMFERENCE = 2 * Math.PI * R;

/** A circular gauge for a 0–100 value. `tone` picks the stroke colour. */
export function ring(value, label, tone = 'accent') {
  const clamped = Math.max(0, Math.min(100, Number(value) || 0));
  const offset = CIRCUMFERENCE * (1 - clamped / 100);
  return html`
    <div class="ring">
      <div class="ring-wrap">
        <svg class="ring-svg" viewBox="0 0 104 104" role="img" aria-label="${label}: ${pct(clamped)}">
          <circle class="ring-track" cx="52" cy="52" r="${R}"/>
          <circle class="ring-fill" cx="52" cy="52" r="${R}"
                  style="stroke: var(--${tone}); stroke-dasharray: ${CIRCUMFERENCE.toFixed(1)}; stroke-dashoffset: ${offset.toFixed(1)}"/>
        </svg>
        <span class="ring-value" aria-hidden="true">${Math.round(clamped)}<small>percent</small></span>
      </div>
      <span class="ring-label">${label}</span>
    </div>`;
}

export function tile(value, label, tone = '') {
  return html`
    <div class="tile ${tone ? `tile-${tone}` : ''}">
      <div class="tile-value">${value}</div>
      <div class="tile-label">${label}</div>
    </div>`;
}

export function empty({ icon: name = 'spark', title, body, action }) {
  return html`
    <div class="empty">
      ${icon(name)}
      <h3>${title}</h3>
      ${body ? html`<p>${body}</p>` : ''}
      ${action ? raw(action) : ''}
    </div>`;
}

export function sectionHead(title, aside = '') {
  return html`
    <div class="section-head">
      <h3>${title}</h3>
      ${aside ? raw(aside) : ''}
    </div>`;
}

/** Placeholder blocks while a pane's data is in flight. */
export function skeleton(rows = 3, height = '5rem') {
  return raw(
    Array.from({ length: rows }, () =>
      `<div class="skeleton" style="height:${escapeHtml(height)};margin-bottom:var(--s-3)"></div>`).join(''),
  );
}

/** A bar whose colour follows the value, for accuracy-like numbers. */
export function accuracyBar(value, tone) {
  const clamped = Math.max(0, Math.min(100, Number(value) || 0));
  return html`<div class="bar bar-${tone}"><i style="width: ${clamped}%"></i></div>`;
}
