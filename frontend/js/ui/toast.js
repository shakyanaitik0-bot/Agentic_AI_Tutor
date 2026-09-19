import { fragment, escapeHtml } from '../lib/dom.js';

const host = document.getElementById('toasts');

const ICONS = { good: 'check', bad: 'close', info: 'spark' };

/** Transient, non-blocking feedback. Errors stay up longer than wins. */
export function toast(message, tone = 'info', ms = tone === 'bad' ? 6000 : 3200) {
  if (!host) return;
  const node = fragment(`
    <div class="toast toast-${escapeHtml(tone)}">
      <svg aria-hidden="true"><use href="#i-${ICONS[tone] || 'spark'}"/></svg>
      <span>${escapeHtml(message)}</span>
    </div>`).firstElementChild;

  host.append(node);
  setTimeout(() => {
    node.classList.add('out');
    node.addEventListener('animationend', () => node.remove(), { once: true });
  }, ms);
}

export const toastOk = (message) => toast(message, 'good');
export const toastErr = (error) => toast(error?.message || String(error), 'bad');
