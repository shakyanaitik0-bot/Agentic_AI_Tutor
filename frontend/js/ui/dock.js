/**
 * The tutor dock.
 *
 * The structural difference from the old console: the tutor is not a
 * tab. It sits beside whatever workspace you are in, so you can ask
 * "why is this the answer?" without leaving the question behind.
 *
 * On narrow screens it becomes a sheet behind a floating button.
 */

import { html, render, raw, icon, $, $$ } from '../lib/dom.js';
import { api } from '../lib/api.js';
import { state, set } from '../lib/store.js';
import { go, emit } from '../lib/bus.js';
import { toastErr } from './toast.js';
import { ensureSession, readableAnswer, handoffFor } from '../lib/session.js';
import { timeOfDay } from '../lib/format.js';

const INTENTS = [
  ['auto', 'Auto', null],
  ['conversation', 'Explain', 'conversation'],
  ['quiz', 'Quiz me', 'quiz'],
  ['plan', 'Plan', 'plan'],
  ['feedback', 'How am I doing', 'feedback'],
];

const SOURCE_LABEL = {
  document: 'Your material',
  web: 'Web',
  knowledge_graph: 'Knowledge graph',
};

const OPENERS = [
  'Explain the intuition behind Bayes’ theorem',
  'Quiz me on what I got wrong last week',
  'Build me a 30-day plan',
  'Where am I weakest right now?',
];

let intent = 'auto';
let host = null;

function citations(list) {
  if (!list?.length) return '';
  return html`
    <div class="cites">
      ${list.slice(0, 4).map((cite) => html`
        <div class="cite">
          <span class="cite-src">${SOURCE_LABEL[cite.source_type] || cite.source_type || 'Source'}${
            cite.relevance_score ? ` · ${Math.round(cite.relevance_score * 100)}% match` : ''
          }</span>
          <span>${cite.title || cite.reference || 'Untitled source'}</span>
        </div>`)}
    </div>`;
}

function bubble(message) {
  if (message.role === 'user') {
    return html`
      <div class="msg msg-user">
        <span class="msg-who">You${message.at ? ` · ${timeOfDay(message.at)}` : ''}</span>
        <div class="msg-body">${message.content}</div>
      </div>`;
  }

  return html`
    <div class="msg msg-tutor">
      <span class="msg-who">${message.agent || 'Tutor'}</span>
      <div class="msg-body">${
        message.pending
          ? raw('<span class="thinking"><i></i><i></i><i></i></span>')
          : message.content
      }</div>
      ${raw(citations(message.citations))}
      ${message.handoff ? html`
        <button class="handoff" data-handoff="${message.handoff.kind}">
          ${icon('spark')}
          <span><strong>${message.handoff.label}</strong><span>${message.handoff.sub}</span></span>
        </button>` : ''}
    </div>`;
}

function conversation() {
  if (!state.messages.length) {
    return html`
      <div class="stack" style="--flow: var(--s-4); margin: auto 0">
        <div>
          <p class="eyebrow">The tutor</p>
          <p class="muted">Ask anything. It routes to the planner, the quiz writer or the feedback agent on its own — or pin the intent with a chip below.</p>
        </div>
        <div class="stack" style="--flow: var(--s-2)">
          ${OPENERS.map((text) => html`
            <button class="handoff" data-opener="${text}" style="border-color: var(--line); background: var(--surface-2)">
              ${icon('chat')}<span><strong>${text}</strong></span>
            </button>`)}
        </div>
      </div>`;
  }
  return raw(state.messages.map(bubble).join(''));
}

function draw() {
  const live = Boolean(state.session?.is_active);

  render(host, html`
    <header class="dock-head">
      ${icon('chat')}
      <strong class="grow">Tutor</strong>
      <span class="dock-status"><span class="dot ${live ? 'dot-live' : ''}"></span>${live ? 'live' : 'idle'}</span>
      <button class="btn btn-quiet btn-sm btn-icon dock-close" data-act="close-dock" aria-label="Close tutor">${icon('close')}</button>
    </header>

    <div class="dock-body scroll" id="dock-body">${raw(conversation())}</div>

    <div class="dock-foot">
      <div class="composer">
        <div class="composer-intents" role="group" aria-label="Route this message">
          ${INTENTS.map(([id, label]) => html`
            <button type="button" data-intent="${id}" aria-pressed="${intent === id}">${label}</button>`)}
        </div>
        <form class="composer-box" id="composer">
          <textarea id="composer-input" rows="1" placeholder="Ask the tutor…" aria-label="Message the tutor"></textarea>
          <button class="btn btn-primary btn-icon" type="submit" aria-label="Send" ${state.tutorBusy ? 'disabled' : ''}>
            ${state.tutorBusy ? raw('<span class="spinner"></span>') : icon('send')}
          </button>
        </form>
      </div>
    </div>`);

  wire();
  const body = $('#dock-body', host);
  if (body) body.scrollTop = body.scrollHeight;
}

function wire() {
  $$('[data-intent]', host).forEach((chip) => chip.addEventListener('click', () => {
    intent = chip.dataset.intent;
    draw();
    $('#composer-input', host)?.focus();
  }));

  $$('[data-opener]', host).forEach((button) => button.addEventListener('click', () => {
    const input = $('#composer-input', host);
    input.value = button.dataset.opener;
    input.focus();
  }));

  $$('[data-handoff]', host).forEach((button) => button.addEventListener('click', () => {
    const message = state.messages.find((item) => item.handoff?.kind === button.dataset.handoff);
    if (!message) return;
    const { kind, payload } = message.handoff;
    go(kind === 'progress' ? 'progress' : kind, { [kind === 'progress' ? 'report' : kind]: payload });
  }));

  $('[data-act="close-dock"]', host)?.addEventListener('click', () => emit('dock:close'));

  const form = $('#composer', host);
  const input = $('#composer-input', host);

  form?.addEventListener('submit', (event) => { event.preventDefault(); send(input.value); });
  input?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      send(input.value);
    }
  });
}

async function send(text) {
  const message = String(text || '').trim();
  if (!message || state.tutorBusy) return;

  const chosen = INTENTS.find(([id]) => id === intent)?.[2] ?? null;

  set({
    messages: [
      ...state.messages,
      { role: 'user', content: message, at: new Date().toISOString() },
      { role: 'tutor', pending: true },
    ],
    tutorBusy: true,
  });
  draw();
  $('#composer-input', host).value = '';

  try {
    await ensureSession();
    const reply = await api.chat.send(state.session.id, message, chosen);
    const agent = reply.agent_response || {};

    const messages = state.messages.slice(0, -1).concat({
      role: 'tutor',
      agent: agent.agent || 'Tutor',
      content: readableAnswer(agent) || 'Answered — the details are in the workspace.',
      citations: agent.citations || [],
      handoff: handoffFor(agent),
    });
    set({ messages, tutorBusy: false });
  } catch (error) {
    set({
      messages: state.messages.slice(0, -1).concat({
        role: 'tutor',
        agent: 'Tutor',
        content: `I could not answer that: ${error.message}`,
      }),
      tutorBusy: false,
    });
    toastErr(error);
  }
  draw();
}

export function mountDock(element) {
  host = element;
  draw();
}

/** Re-render when another part of the app changed the transcript. */
export function refreshDock() {
  if (host) draw();
}

/** Put a question in the composer and focus it — used by the palette. */
export function askTutor(prefill = '') {
  emit('dock:open');
  queueMicrotask(() => {
    const input = $('#composer-input', host);
    if (!input) return;
    input.value = prefill;
    input.focus();
  });
}
