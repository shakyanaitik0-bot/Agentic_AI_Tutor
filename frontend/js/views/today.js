/**
 * Today — the landing workspace.
 *
 * Replaces the old row of grey buttons with an answer to "what should I
 * do right now": whatever is due, whatever the plan says, whatever the
 * feedback agent flagged.
 */

import { html, render, raw, icon, $, $$ } from '../lib/dom.js';
import { api } from '../lib/api.js';
import { state, set, dueCardCount } from '../lib/store.js';
import { go } from '../lib/bus.js';
import { ring, tile, sectionHead } from '../ui/bits.js';
import { toastErr } from '../ui/toast.js';
import { greeting, hours } from '../lib/format.js';
import { endSession, startSession } from '../lib/session.js';

export const meta = {
  id: 'today',
  label: 'Today',
  icon: 'today',
  title: 'Today',
  subtitle: 'What is worth doing next',
};

const QUICK = [
  ['quiz', 'quiz', 'Take a quiz', 'Difficulty adapts to your accuracy'],
  ['cards', 'cards', 'Review cards', 'Spaced repetition, keyboard graded'],
  ['plan', 'plan', 'Build a study plan', 'Day-by-day, weighted to weak areas'],
  ['library', 'library', 'Add material', 'Ground answers in your own notes'],
];

/** Pull everything Today shows. Individual failures are survivable. */
async function load() {
  const id = state.student.id;
  const [report, stats, decks, plan] = await Promise.all([
    api.feedback.report(id).catch(() => null),
    api.flashcards.stats(id).catch(() => null),
    api.flashcards.decks(id).catch(() => []),
    api.plan.latest(id).catch(() => null),
  ]);
  set({ report, cardStats: stats, decks: decks || [], plan });
}

function hero() {
  const { student, session } = state;
  const live = Boolean(session?.is_active);
  return html`
    <section class="hero">
      <div class="spread" style="align-items: flex-start; flex-wrap: wrap">
        <div>
          <p class="eyebrow">${live ? 'Session open' : 'Session closed'}</p>
          <h2 class="hero-greet">${greeting()}, ${student.name.split(' ')[0]}.</h2>
          <p class="muted">Preparing for ${student.exam_type}${
            student.weak_areas?.length ? ` · weakest right now: ${student.weak_areas.slice(0, 3).join(', ')}` : ''
          }</p>
        </div>
        <div class="row-wrap">
          <span class="dock-status"><span class="dot ${live ? 'dot-live' : ''}"></span>${
            live ? `${session.questions_asked || 0} asked this session` : 'Not started'
          }</span>
          ${live
            ? html`<button class="btn btn-ghost btn-sm" data-act="end-session">End session</button>`
            : html`<button class="btn btn-primary btn-sm" data-act="start-session">Start a session</button>`}
        </div>
      </div>
    </section>`;
}

function gauges() {
  const stats = state.report?.overall_stats;
  const cards = state.cardStats;
  if (!stats && !cards) return '';

  return html`
    <section class="card">
      <div class="rings">
        ${ring(stats?.overall_accuracy ?? 0, 'Quiz accuracy', 'accent')}
        ${ring(cards?.mastery_percentage ?? 0, 'Card mastery', 'cool')}
        ${ring(cards?.accuracy_this_week ?? 0, 'Card accuracy, 7d', 'good')}
      </div>
      ${stats ? html`
        <div class="tiles" style="margin-top: var(--s-5)">
          ${tile(stats.total_attempts ?? 0, 'Questions attempted')}
          ${tile(stats.total_topics ?? 0, 'Topics touched')}
          ${tile(hours((stats.total_time_minutes ?? 0) / 60), 'Time studied')}
          ${tile(stats.weak_topics_count ?? 0, 'Weak topics', stats.weak_topics_count ? 'bad' : '')}
        </div>` : ''}
    </section>`;
}

function dueBanner() {
  const due = dueCardCount();
  if (!due) return '';
  return html`
    <button class="card card-lift" data-act="study-due" style="display: block; width: 100%; text-align: left; border-color: var(--accent-line)">
      <div class="spread">
        <div class="row">
          ${icon('cards', 'icon-lg')}
          <div>
            <strong>${due} card${due === 1 ? '' : 's'} due for review</strong>
            <p class="muted" style="font-size: var(--step--1)">Reviewing on schedule is what makes the scheduling worth anything.</p>
          </div>
        </div>
        <span class="pill pill-accent">Review now</span>
      </div>
    </button>`;
}

function planPeek() {
  const plan = state.plan;
  if (!plan?.daily_schedule?.length) {
    return html`
      <section class="card">
        ${sectionHead('Study plan')}
        <p class="muted">No plan yet. The planner reads your weak areas and lays out a day-by-day schedule.</p>
        <button class="btn btn-ghost btn-sm" data-go="plan" style="margin-top: var(--s-4)">Build one</button>
      </section>`;
  }

  const days = plan.daily_schedule.slice(0, 3);
  return html`
    <section class="card">
      ${sectionHead('Study plan', `<button class="btn btn-quiet btn-sm" data-go="plan">See all ${plan.timeline_days} days</button>`)}
      <div class="timeline">
        ${days.map((day) => html`
          <article class="day">
            <div class="spread">
              <span class="day-n">Day ${day.day}${day.date ? ` · ${day.date}` : ''}</span>
              <span class="pill">${hours(day.hours_allocated)}</span>
            </div>
            <p style="margin-top: var(--s-2)">${day.topics.join(' · ')}</p>
          </article>`)}
      </div>
    </section>`;
}

function recommendations() {
  const list = state.report?.recommendations || [];
  if (!list.length) return '';
  return html`
    <section class="card">
      ${sectionHead('What the feedback agent suggests', `<button class="btn btn-quiet btn-sm" data-go="progress">Full report</button>`)}
      ${list.slice(0, 4).map((item, i) => html`
        <div class="rec"><span class="rec-n">${String(i + 1).padStart(2, '0')}</span><span>${item}</span></div>`)}
    </section>`;
}

function quickActions() {
  return html`
    <section>
      ${sectionHead('Jump in')}
      <div class="quick">
        ${QUICK.map(([view, iconName, title, sub]) => html`
          <button class="quick-btn" data-go="${view}">
            ${icon(iconName)}
            <strong>${title}</strong>
            <span>${sub}</span>
          </button>`)}
      </div>
    </section>`;
}

function draw(host) {
  render(host, html`
    <div class="pane scroll">
      <div class="pane-inner stack" style="--flow: var(--s-5)">
        ${raw(hero())}
        ${raw(dueBanner())}
        ${raw(gauges())}
        ${raw(quickActions())}
        ${raw(planPeek())}
        ${raw(recommendations())}
      </div>
    </div>`);

  $$('[data-go]', host).forEach((button) => button.addEventListener('click', () => go(button.dataset.go)));

  $('[data-act="study-due"]', host)?.addEventListener('click', () => {
    const deck = state.decks.find((item) => item.due_count > 0) || state.decks[0];
    go('cards', deck ? { study: deck.id } : null);
  });

  $('[data-act="start-session"]', host)?.addEventListener('click', async (event) => {
    event.currentTarget.disabled = true;
    try { await startSession(); draw(host); } catch (error) { toastErr(error); event.currentTarget.disabled = false; }
  });

  $('[data-act="end-session"]', host)?.addEventListener('click', async (event) => {
    event.currentTarget.disabled = true;
    try { await endSession(); draw(host); } catch (error) { toastErr(error); event.currentTarget.disabled = false; }
  });
}

export async function mount(host) {
  draw(host);                       // paint immediately from whatever is cached
  try {
    await load();
  } catch (error) {
    toastErr(error);
  }
  draw(host);
}
