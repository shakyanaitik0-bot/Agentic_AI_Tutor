/**
 * Flashcards — decks, and a review loop you drive from the keyboard.
 *
 * Space flips, 0–5 grades, Escape leaves. The backend hides each answer
 * until you ask for it (`/card/{id}/reveal`), which keeps the self-test
 * honest, so revealing is a real request and the card says so.
 */

import { html, render, raw, icon, $, $$ } from '../lib/dom.js';
import { api } from '../lib/api.js';
import { state, set } from '../lib/store.js';
import { toast, toastErr } from '../ui/toast.js';
import { empty, sectionHead, tile } from '../ui/bits.js';
import { titleCase } from '../lib/format.js';

export const meta = {
  id: 'cards',
  label: 'Cards',
  icon: 'cards',
  title: 'Flashcards',
  subtitle: 'Spaced repetition, SM-2',
};

const GRADES = [
  [0, 'Blank', 'grade-0'],
  [1, 'Wrong', 'grade-1'],
  [2, 'Shaky', 'grade-2'],
  [3, 'Hard', 'grade-3'],
  [4, 'Good', 'grade-4'],
  [5, 'Easy', 'grade-5'],
];

let keyHandler = null;

/* ── deck list ────────────────────────────────────────────────── */

function deckCard(deck) {
  const mastery = deck.card_count ? (deck.mastered_count / deck.card_count) * 100 : 0;
  return html`
    <article class="card card-lift deck">
      <div>
        <div class="spread" style="align-items: flex-start">
          <h3 style="font-size: var(--step-1)">${deck.name}</h3>
          ${deck.due_count ? html`<span class="pill pill-accent">${deck.due_count} due</span>` : ''}
        </div>
        <p class="deck-topic">${deck.topic}</p>
      </div>

      <div class="deck-meter">
        <div class="bar bar-cool"><i style="width: ${mastery}%"></i></div>
        <div class="deck-nums muted">
          <span><b>${deck.card_count}</b> cards</span>
          <span><b>${deck.mastered_count}</b> mastered</span>
          <span><b>${deck.new_count}</b> new</span>
        </div>
      </div>

      <div class="row">
        <button class="btn btn-primary btn-sm grow" data-study="${deck.id}">
          ${deck.due_count ? 'Review due' : 'Study deck'}
        </button>
        <button class="btn btn-quiet btn-sm btn-icon" data-delete="${deck.id}" aria-label="Delete ${deck.name}" title="Delete deck">
          ${icon('trash')}
        </button>
      </div>
    </article>`;
}

function listScreen() {
  const stats = state.cardStats;
  return html`
    <div class="pane-inner stack" style="--flow: var(--s-5)">
      ${stats ? html`
        <div class="tiles">
          ${tile(stats.total_due ?? 0, 'Due now', stats.total_due ? 'accent' : '')}
          ${tile(stats.total_cards ?? 0, 'Cards total')}
          ${tile(`${Math.round(stats.mastery_percentage ?? 0)}%`, 'Mastered', 'cool')}
          ${tile(stats.reviews_this_week ?? 0, 'Reviews, 7 days')}
        </div>` : ''}

      <section class="card">
        <div class="card-head">
          <div>
            <p class="eyebrow">New deck</p>
            <h2>Generate cards</h2>
          </div>
        </div>
        <form id="deck-form" class="stack" style="--flow: var(--s-4)">
          <div class="field">
            <label for="fc-topic">Topic</label>
            <input class="input" id="fc-topic" name="topic" required placeholder="Organic reaction mechanisms, Cell respiration…">
          </div>
          <div class="field-row">
            <div class="field">
              <label for="fc-count">Cards</label>
              <select class="select" id="fc-count" name="num">
                ${[5, 10, 15, 20, 30].map((n) => html`<option value="${n}" ${n === 10 ? 'selected' : ''}>${n}</option>`)}
              </select>
            </div>
            <div class="field">
              <label for="fc-diff">Difficulty</label>
              <select class="select" id="fc-diff" name="difficulty">
                ${['easy', 'medium', 'hard'].map((level) => html`
                  <option value="${level}" ${level === 'medium' ? 'selected' : ''}>${titleCase(level)}</option>`)}
              </select>
            </div>
          </div>
          <label class="check">
            <input type="checkbox" name="useDocs" checked>
            <span>Draw from my uploaded material when it covers the topic</span>
          </label>
          <button class="btn btn-primary" type="submit" data-submit>${icon('spark')} Generate deck</button>
        </form>
      </section>

      <section>
        ${sectionHead('Your decks', state.decks.length ? `<span class="muted" style="font-size:var(--step--1)">${state.decks.length} deck${state.decks.length === 1 ? '' : 's'}</span>` : '')}
        ${state.decks.length
          ? html`<div class="deck-grid">${state.decks.map((deck) => raw(deckCard(deck)))}</div>`
          : empty({ icon: 'cards', title: 'No decks yet', body: 'Generate one above. Cards you get right come back later, cards you miss come back sooner.' })}
      </section>
    </div>`;
}

/* ── study loop ───────────────────────────────────────────────── */

function studyScreen() {
  const study = state.study;

  if (study.index >= study.cards.length) {
    return html`
      <div class="pane-inner">
        <section class="card">
          <div class="score-hero">
            ${icon('check', 'icon-lg')}
            <h2>Deck cleared</h2>
            <p class="muted">${study.reviewed} card${study.reviewed === 1 ? '' : 's'} reviewed in ${study.deckName}. Scheduling updated.</p>
            <div class="row-wrap" style="justify-content: center">
              <button class="btn btn-primary" data-act="exit">Back to decks</button>
            </div>
          </div>
        </section>
      </div>`;
  }

  const card = study.cards[study.index];
  const progress = (study.index / study.cards.length) * 100;

  return html`
    <div class="pane-inner stack" style="--flow: var(--s-4)">
      <div class="spread">
        <div class="row-wrap">
          <span class="pill pill-cool">${study.deckName}</span>
          ${card.topic ? html`<span class="pill">${card.topic}</span>` : ''}
          ${card.is_due ? html`<span class="pill pill-accent">Due</span>` : html`<span class="pill">New</span>`}
        </div>
        <span class="quiz-count mono">${study.index + 1} / ${study.cards.length}</span>
      </div>
      <div class="bar bar-cool"><i style="width: ${progress}%"></i></div>

      <div class="flip-stage">
        <div class="flip ${study.revealed ? 'is-back' : ''}" data-act="flip" role="button" tabindex="0"
             aria-label="${study.revealed ? 'Answer shown' : 'Show the answer'}">
          <div class="flip-face">
            <span class="eyebrow">${titleCase(card.type || 'card')}</span>
            <p class="flip-text">${card.front}</p>
            ${card.hints?.length ? html`<p class="flip-hint">Hint: ${card.hints[0]}</p>` : ''}
            <p class="flip-hint"><span class="kbd">Space</span> to reveal</p>
          </div>
          <div class="flip-face flip-back">
            <span class="eyebrow">Answer</span>
            <p class="flip-text">${study.back ?? '…'}</p>
            ${study.source ? html`<p class="flip-hint">Source: ${study.source}</p>` : ''}
          </div>
        </div>
      </div>

      ${study.revealed ? html`
        <div class="stack" style="--flow: var(--s-2)">
          <p class="field-hint">How did that go? Keys <span class="kbd">0</span>–<span class="kbd">5</span>.</p>
          <div class="grades">
            ${GRADES.map(([value, label, cls]) => html`
              <button class="grade ${cls}" data-grade="${value}"><b>${value}</b><span>${label}</span></button>`)}
          </div>
        </div>`
        : html`<button class="btn btn-primary btn-lg btn-block" data-act="flip">Reveal answer</button>`}

      <button class="btn btn-quiet btn-sm" data-act="exit">Leave this deck</button>
    </div>`;
}

/* ── actions ──────────────────────────────────────────────────── */

async function refreshDecks() {
  const [decks, stats] = await Promise.all([
    api.flashcards.decks(state.student.id).catch(() => []),
    api.flashcards.stats(state.student.id).catch(() => null),
  ]);
  set({ decks: decks || [], cardStats: stats });
}

async function beginStudy(host, deckId) {
  try {
    const session = await api.flashcards.study(deckId, { maxCards: 20, includeNew: true });
    if (!session.cards.length) {
      toast('Nothing due in this deck yet. Come back when it is.', 'info');
      return;
    }
    set({
      study: {
        deckId: session.deck_id,
        deckName: session.deck_name,
        cards: session.cards,
        index: 0,
        revealed: false,
        back: null,
        source: null,
        reviewed: 0,
        shownAt: Date.now(),
      },
    });
    draw(host);
  } catch (error) {
    toastErr(error);
  }
}

async function reveal(host) {
  const study = state.study;
  if (!study || study.revealed) return;
  const card = study.cards[study.index];

  set({ study: { ...study, revealed: true, back: card.back ?? null } });
  draw(host);

  if (card.back == null) {
    try {
      const full = await api.flashcards.reveal(card.id);
      set({ study: { ...state.study, back: full.back, source: full.source || null } });
      draw(host);
    } catch (error) {
      toastErr(error);
    }
  }
}

async function grade(host, quality) {
  const study = state.study;
  if (!study?.revealed) return;
  const card = study.cards[study.index];

  set({
    study: {
      ...study,
      index: study.index + 1,
      revealed: false,
      back: null,
      source: null,
      reviewed: study.reviewed + 1,
      shownAt: Date.now(),
    },
  });
  draw(host);

  try {
    await api.flashcards.review({
      cardId: card.id,
      quality,
      responseTimeMs: Date.now() - study.shownAt,
    });
  } catch (error) {
    toastErr(error);          // the card already advanced; surface but do not block
  }
}

async function generate(host, form) {
  const data = Object.fromEntries(new FormData(form));
  if (!data.topic || !String(data.topic).trim()) return toastErr(new Error('Give the deck a topic first.'));

  const button = $('[data-submit]', form);
  button.disabled = true;
  button.innerHTML = '<span class="spinner"></span> Writing cards…';

  try {
    const deck = await api.flashcards.generate(state.student.id, {
      topic: String(data.topic).trim(),
      numCards: Number(data.num),
      difficulty: data.difficulty,
      useDocuments: data.useDocs === 'on',
    });
    toast(`"${deck.name}" is ready — ${deck.card_count} cards.`, 'good');
    await refreshDecks();
    draw(host);
  } catch (error) {
    toastErr(error);
    button.disabled = false;
    button.textContent = 'Generate deck';
  }
}

function bindKeys(host) {
  unbindKeys();
  keyHandler = (event) => {
    if (!state.study) return;
    if (event.target.matches('input, textarea, select')) return;

    if (event.key === 'Escape') { set({ study: null }); draw(host); return; }
    if (state.study.index >= state.study.cards.length) return;

    if (!state.study.revealed && (event.key === ' ' || event.key === 'Enter')) {
      event.preventDefault();
      reveal(host);
      return;
    }
    if (state.study.revealed && /^[0-5]$/.test(event.key)) {
      event.preventDefault();
      grade(host, Number(event.key));
    }
  };
  window.addEventListener('keydown', keyHandler);
}

function unbindKeys() {
  if (keyHandler) window.removeEventListener('keydown', keyHandler);
  keyHandler = null;
}

function draw(host) {
  render(host, html`<div class="pane scroll">${raw(state.study ? studyScreen() : listScreen())}</div>`);

  if (state.study) bindKeys(host); else unbindKeys();

  const form = $('#deck-form', host);
  form?.addEventListener('submit', (event) => { event.preventDefault(); generate(host, form); });

  $$('[data-study]', host).forEach((button) =>
    button.addEventListener('click', () => beginStudy(host, button.dataset.study)));

  $$('[data-delete]', host).forEach((button) =>
    button.addEventListener('click', async () => {
      const deck = state.decks.find((item) => item.id === button.dataset.delete);
      if (!window.confirm(`Delete "${deck?.name ?? 'this deck'}" and every card in it?`)) return;
      try {
        await api.flashcards.deleteDeck(button.dataset.delete);
        toast('Deck deleted.', 'good');
        await refreshDecks();
        draw(host);
      } catch (error) { toastErr(error); }
    }));

  $$('[data-act="flip"]', host).forEach((el) => {
    el.addEventListener('click', () => reveal(host));
    el.addEventListener('keydown', (event) => {
      if (event.key === ' ' || event.key === 'Enter') { event.preventDefault(); reveal(host); }
    });
  });

  $$('[data-grade]', host).forEach((button) =>
    button.addEventListener('click', () => grade(host, Number(button.dataset.grade))));

  $$('[data-act="exit"]', host).forEach((button) =>
    button.addEventListener('click', async () => {
      set({ study: null });
      await refreshDecks();
      draw(host);
    }));
}

/** `payload.study` starts a deck straight away — used by Today's due banner. */
export async function mount(host, payload) {
  draw(host);
  await refreshDecks();
  if (payload?.study) { await beginStudy(host, payload.study); return; }
  draw(host);
}

export function unmount() {
  unbindKeys();
}
