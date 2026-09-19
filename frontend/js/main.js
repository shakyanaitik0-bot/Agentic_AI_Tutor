/**
 * Shell: rail, workspace, tutor dock.
 *
 * Boots by restoring a stored identity, then routes off the hash so a
 * reload lands you where you were — the old console dropped you back at
 * the login form every time.
 */

import { html, render, icon, $, $$ } from './lib/dom.js';
import { api, setAuthToken, setUnauthorizedHandler } from './lib/api.js';
import {
  state, set, subscribe, persist, readPersisted, clearPersisted,
  readTheme, applyTheme, toggleTheme, dueCardCount,
} from './lib/store.js';
import { on as onBus, emit, go } from './lib/bus.js';
import { restoreOrStart, endSession, startSession } from './lib/session.js';
import { mountAuth } from './views/auth.js';
import { mountDock, refreshDock, askTutor } from './ui/dock.js';
import { openPalette, close as closePalette, handleKey as paletteKey, isOpen as paletteOpen, setCommands } from './ui/palette.js';
import { toast, toastErr } from './ui/toast.js';

import * as today from './views/today.js';
import * as quiz from './views/quiz.js';
import * as cards from './views/cards.js';
import * as plan from './views/plan.js';
import * as progress from './views/progress.js';
import * as library from './views/library.js';

const VIEWS = [today, quiz, cards, plan, progress, library];
const BY_ID = new Map(VIEWS.map((view) => [view.meta.id, view]));

const root = document.getElementById('app');
let current = null;         // the mounted view module
let paneRoot = null;

/* ── routing ──────────────────────────────────────────────────── */

const viewFromHash = () => {
  const id = location.hash.replace(/^#\/?/, '');
  return BY_ID.has(id) ? id : 'today';
};

function navigate(id, payload = null) {
  if (!BY_ID.has(id)) id = 'today';
  if (location.hash !== `#/${id}`) {
    history.pushState(null, '', `#/${id}`);
  }
  mountView(id, payload);
}

function mountView(id, payload) {
  current?.unmount?.();
  const view = BY_ID.get(id);
  current = view;

  $$('.rail-btn[data-view]').forEach((button) => {
    button.setAttribute('aria-current', button.dataset.view === id ? 'page' : 'false');
  });

  const bar = $('#topbar-title');
  if (bar) {
    bar.textContent = view.meta.title;
    $('#topbar-sub').textContent = view.meta.subtitle;
  }

  // A fresh host per mount: a request that resolves after the user has
  // navigated away then paints into a detached node instead of over the
  // workspace they are now looking at.
  const host = document.createElement('div');
  host.className = 'pane-host';
  paneRoot.replaceChildren(host);

  view.mount(host, payload);
  if (window.innerWidth <= 720) emit('dock:close');
}

/* ── shell chrome ─────────────────────────────────────────────── */

function railButton(view) {
  const due = view.meta.id === 'cards' ? dueCardCount() : 0;
  return html`
    <button class="rail-btn" data-view="${view.meta.id}" aria-current="false" aria-label="${view.meta.label}">
      ${icon(view.meta.icon)}
      ${due ? html`<span class="badge">${due > 99 ? '99+' : due}</span>` : ''}
      <span class="rail-tip">${view.meta.label}</span>
    </button>`;
}

function shell() {
  return html`
    <div class="shell" id="shell" data-dock="closed">
      <nav class="rail" aria-label="Workspaces">
        <span class="rail-mark" aria-hidden="true">AT</span>
        ${VIEWS.map(railButton)}
        <span class="rail-spacer"></span>
        <button class="rail-btn rail-only-desktop" data-act="palette" aria-label="Command palette">
          ${icon('search')}<span class="rail-tip">Search · ⌘K</span>
        </button>
        <button class="rail-btn" data-act="theme" aria-label="Switch theme">
          ${icon(document.documentElement.dataset.theme === 'light' ? 'moon' : 'sun')}
          <span class="rail-tip">Theme</span>
        </button>
        <button class="rail-btn" data-act="signout" aria-label="Sign out">
          ${icon('logout')}<span class="rail-tip">Sign out</span>
        </button>
      </nav>

      <main class="workspace">
        <header class="topbar">
          <div class="grow">
            <h1 id="topbar-title">Today</h1>
            <p class="topbar-sub" id="topbar-sub">What is worth doing next</p>
          </div>
          <button class="btn btn-ghost btn-sm rail-only-desktop" data-act="palette">
            ${icon('search')} Search <span class="kbd">⌘K</span>
          </button>
        </header>
        <div id="pane"></div>
      </main>

      <aside class="dock" id="dock" aria-label="Tutor"></aside>
      <div class="dock-scrim" data-act="close-dock"></div>
      <button class="dock-toggle" data-act="open-dock" aria-label="Open the tutor">
        ${icon('chat')}<span class="badge"></span>
      </button>
    </div>`;
}

function wireShell() {
  $$('.rail-btn[data-view]').forEach((button) =>
    button.addEventListener('click', () => navigate(button.dataset.view)));

  $$('[data-act="palette"]').forEach((button) => button.addEventListener('click', openPalette));

  $$('[data-act="theme"]').forEach((button) => button.addEventListener('click', () => {
    const theme = toggleTheme();
    const use = button.querySelector('use');
    use?.setAttribute('href', theme === 'light' ? '#i-moon' : '#i-sun');
  }));

  $$('[data-act="signout"]').forEach((button) => button.addEventListener('click', signOut));
  $$('[data-act="open-dock"]').forEach((button) => button.addEventListener('click', () => emit('dock:open')));
  $$('[data-act="close-dock"]').forEach((button) => button.addEventListener('click', () => emit('dock:close')));
}

function setDock(open) {
  $('#shell')?.setAttribute('data-dock', open ? 'open' : 'closed');
}

/* ── commands ─────────────────────────────────────────────────── */

function buildCommands() {
  const commands = VIEWS.map((view) => ({
    label: `Go to ${view.meta.label}`,
    hint: view.meta.subtitle,
    icon: view.meta.icon,
    keywords: view.meta.id,
    run: () => navigate(view.meta.id),
  }));

  commands.push(
    { label: 'Ask the tutor', hint: 'Open the dock with the cursor in the box', icon: 'chat', keywords: 'chat message question', run: () => askTutor() },
    { label: 'Quiz me on my weakest topic', icon: 'quiz', keywords: 'practice test', run: () => askTutor('Quiz me on whatever I am weakest at right now.') },
    { label: 'Build a 30-day study plan', icon: 'plan', keywords: 'schedule timeline', run: () => askTutor('Build me a 30-day study plan.') },
    { label: 'Switch theme', icon: document.documentElement.dataset.theme === 'light' ? 'moon' : 'sun', keywords: 'dark light appearance', run: () => { toggleTheme(); drawShell(); } },
    state.session?.is_active
      ? { label: 'End this session', icon: 'close', keywords: 'stop finish', run: () => endSession().then(drawShell).catch(toastErr) }
      : { label: 'Start a session', icon: 'spark', keywords: 'begin', run: () => startSession().then(drawShell).catch(toastErr) },
    { label: 'Sign out', icon: 'logout', keywords: 'logout leave', run: signOut },
  );

  setCommands(commands);
}

/* ── lifecycle ────────────────────────────────────────────────── */

function drawShell() {
  const activeId = current?.meta?.id || viewFromHash();
  render(root, shell());
  root.classList.remove('app-boot');
  paneRoot = $('#pane');
  wireShell();
  mountDock($('#dock'));
  buildCommands();
  mountView(activeId, null);
}

function signOut() {
  clearPersisted();
  setAuthToken(null);
  set({
    student: null, session: null, messages: [], quiz: null, quizAnswers: [],
    quizResult: null, plan: null, report: null, decks: [], cardStats: null,
    study: null, documents: [],
  });
  current = null;
  history.replaceState(null, '', location.pathname + location.search);
  showAuth();
}

function showAuth() {
  root.classList.remove('app-boot');
  mountAuth(root, async (student) => {
    // The login response carries JWT fields once the backend issues them.
    if (student.access_token) setAuthToken(student.access_token);
    set({ student });
    persist();
    try {
      await restoreOrStart();
    } catch (error) {
      toastErr(error);       // the console still works; chat will retry on send
    }
    drawShell();
    toast(`Signed in as ${student.name}.`, 'good');
  });
}

async function boot() {
  applyTheme(readTheme());
  setUnauthorizedHandler(() => {
    if (!state.student) return;
    toast('Your sign-in expired. Signing you back in.', 'info');
    signOut();
  });

  const { studentId, sessionId } = readPersisted();
  if (!studentId) return showAuth();

  try {
    const student = await api.students.get(studentId);
    set({ student });
    await restoreOrStart(sessionId);
    drawShell();
  } catch (error) {
    clearPersisted();
    if (error.status === 0) toastErr(error);
    showAuth();
  }
}

/* ── global wiring ────────────────────────────────────────────── */

onBus('go', ({ view, payload }) => navigate(view, payload));
onBus('dock:open', () => setDock(true));
onBus('dock:close', () => setDock(false));

subscribe(() => {
  // The rail's due-card badge and the dock share state; keep both honest.
  const badge = dueCardCount();
  $$('.rail-btn[data-view="cards"] .badge').forEach((el) => {
    el.textContent = badge > 99 ? '99+' : String(badge);
    el.classList.toggle('hidden', badge === 0);
  });
});

window.addEventListener('popstate', () => { if (state.student) mountView(viewFromHash(), null); });

window.addEventListener('keydown', (event) => {
  if (paletteKey(event)) return;

  const mod = event.metaKey || event.ctrlKey;
  if (mod && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    paletteOpen() ? closePalette() : openPalette();
    return;
  }
  if (!state.student) return;

  // "/" focuses the tutor, the way it does in most reading tools.
  if (event.key === '/' && !event.target.matches('input, textarea, select')) {
    event.preventDefault();
    askTutor();
  }
});

// Keep the dock in sync when a workspace mutates the transcript.
subscribe(() => refreshDock());

boot();
