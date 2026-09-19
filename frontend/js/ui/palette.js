/**
 * Command palette — ⌘K / Ctrl+K.
 *
 * Everything the rail does, plus the actions buried inside workspaces,
 * reachable without hunting for a button.
 */

import { html, render, raw, icon, $, $$ } from '../lib/dom.js';

let overlay = null;
let commands = [];
let filtered = [];
let selected = 0;

function score(command, query) {
  if (!query) return 1;
  const haystack = `${command.label} ${command.hint || ''} ${command.keywords || ''}`.toLowerCase();
  const needle = query.toLowerCase();
  if (haystack.startsWith(needle)) return 3;
  if (haystack.includes(needle)) return 2;
  // loose subsequence match, so "opq" finds "Open quiz"
  let i = 0;
  for (const ch of haystack) if (ch === needle[i]) i += 1;
  return i === needle.length ? 1 : 0;
}

function list() {
  if (!filtered.length) {
    return html`<p class="palette-empty">Nothing matches that.</p>`;
  }
  return raw(filtered.map((command, i) => html`
    <button class="palette-item" data-run="${i}" aria-selected="${i === selected}">
      ${icon(command.icon || 'spark')}
      <span class="grow">
        <span>${command.label}</span>
        ${command.hint ? html`<br><span class="sub">${command.hint}</span>` : ''}
      </span>
      ${command.keys ? html`<span class="kbd">${command.keys}</span>` : ''}
    </button>`).join(''));
}

function draw(query = '') {
  render(overlay, html`
    <div class="palette" role="dialog" aria-modal="true" aria-label="Command palette">
      <div class="palette-input">
        ${icon('search')}
        <input id="palette-query" type="text" placeholder="Jump to, or do…" value="${query}" autocomplete="off" spellcheck="false">
      </div>
      <div class="palette-list" id="palette-list">${raw(list())}</div>
    </div>`);

  const input = $('#palette-query', overlay);
  input.focus();
  input.setSelectionRange(query.length, query.length);
  input.addEventListener('input', () => filter(input.value));

  $$('[data-run]', overlay).forEach((item) =>
    item.addEventListener('click', () => run(Number(item.dataset.run))));
}

function filter(query) {
  filtered = commands
    .map((command) => ({ command, rank: score(command, query.trim()) }))
    .filter((entry) => entry.rank > 0)
    .sort((a, b) => b.rank - a.rank)
    .map((entry) => entry.command);
  selected = 0;
  draw(query);
}

function move(delta) {
  if (!filtered.length) return;
  selected = (selected + delta + filtered.length) % filtered.length;
  $$('[data-run]', overlay).forEach((item, i) => item.setAttribute('aria-selected', String(i === selected)));
  $$('[data-run]', overlay)[selected]?.scrollIntoView({ block: 'nearest' });
}

function run(index) {
  const command = filtered[index];
  close();
  command?.run();
}

export function openPalette() {
  if (overlay) return;
  overlay = document.createElement('div');
  overlay.className = 'palette-scrim';
  overlay.addEventListener('mousedown', (event) => { if (event.target === overlay) close(); });
  document.body.append(overlay);
  filter('');
}

export function close() {
  overlay?.remove();
  overlay = null;
}

export const isOpen = () => Boolean(overlay);

/** Register the command set. Called once by the shell. */
export function setCommands(next) {
  commands = next;
}

/** Key handling for the palette itself; the shell owns the open shortcut. */
export function handleKey(event) {
  if (!overlay) return false;
  if (event.key === 'Escape') { close(); return true; }
  if (event.key === 'ArrowDown') { event.preventDefault(); move(1); return true; }
  if (event.key === 'ArrowUp') { event.preventDefault(); move(-1); return true; }
  if (event.key === 'Enter') { event.preventDefault(); run(selected); return true; }
  return false;
}
