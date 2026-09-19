/**
 * Progress — the feedback agent's report, arranged so the weak topics
 * are the first thing on screen and everything else is optional depth.
 */

import { html, render, raw, icon, $, $$ } from '../lib/dom.js';
import { api } from '../lib/api.js';
import { state, set } from '../lib/store.js';
import { go } from '../lib/bus.js';
import { toastErr } from '../ui/toast.js';
import { empty, ring, tile, sectionHead, accuracyBar } from '../ui/bits.js';
import { accuracyTone, hours, pct, titleCase } from '../lib/format.js';

export const meta = {
  id: 'progress',
  label: 'Progress',
  icon: 'progress',
  title: 'Progress',
  subtitle: 'Where the evidence says you stand',
};

let group = 'weak';

const GROUPS = [
  ['weak', 'Needs work', 'weak_topics'],
  ['strong', 'Solid', 'strong_topics'],
  ['improving', 'Improving', 'improving_topics'],
  ['declining', 'Slipping', 'declining_topics'],
];

function topicCard(topic) {
  const tone = accuracyTone(topic.accuracy);
  const rising = Number(topic.trend_value) > 0;
  return html`
    <article class="topic-card">
      <div class="spread" style="align-items: flex-start">
        <div>
          <div class="row-wrap">
            <strong>${topic.topic}</strong>
            <span class="pill">${titleCase(topic.difficulty)}</span>
            ${topic.mastery_achieved ? html`<span class="pill pill-good">Mastered</span>` : ''}
            ${topic.needs_review ? html`<span class="pill pill-warn">Review due</span>` : ''}
          </div>
        </div>
        <span class="mono" style="font-size: var(--step-1); font-weight: 700; color: var(--${tone})">${pct(topic.accuracy)}</span>
      </div>

      ${accuracyBar(topic.accuracy, tone)}

      <div class="topic-meta">
        <span>${topic.correct}/${topic.attempts} correct</span>
        <span>${hours((topic.time_spent_minutes || 0) / 60)} spent</span>
        <span>streak ${topic.consecutive_correct} · best ${topic.max_streak}</span>
        <span>last practised ${topic.days_since_practice === 0 ? 'today' : `${topic.days_since_practice}d ago`}</span>
        <span class="${rising ? 'trend-up' : Number(topic.trend_value) < 0 ? 'trend-down' : ''}">
          ${titleCase(topic.trend)}${topic.trend_value ? ` ${rising ? '+' : ''}${Math.round(topic.trend_value)}` : ''}
        </span>
      </div>

      ${topic.common_mistakes?.length ? html`
        <p class="muted" style="font-size: var(--step--1)">Pattern: ${topic.common_mistakes.join('; ')}</p>` : ''}

      <div>
        <button class="btn btn-ghost btn-sm" data-drill="${topic.topic}">Quiz me on this</button>
      </div>
    </article>`;
}

function screen() {
  const report = state.report;

  if (!report) {
    return html`
      <div class="pane-inner">
        ${empty({
          icon: 'progress',
          title: 'Nothing measured yet',
          body: 'Take a quiz or review a deck. Accuracy, trends and weak-topic detection all come from attempts.',
          action: '<button class="btn btn-primary btn-sm" data-go="quiz">Take a quiz</button>',
        })}
      </div>`;
  }

  const stats = report.overall_stats;
  const key = GROUPS.find(([id]) => id === group)[2];
  const topics = report[key] || [];

  return html`
    <div class="pane-inner stack" style="--flow: var(--s-5)">
      <section class="card">
        <div class="rings">
          ${ring(stats.overall_accuracy, 'Overall accuracy', accuracyTone(stats.overall_accuracy))}
          ${ring(stats.total_topics ? (stats.mastery_topics_count / stats.total_topics) * 100 : 0, 'Topics mastered', 'cool')}
          ${ring(stats.total_topics ? (stats.recently_practiced_count / stats.total_topics) * 100 : 0, 'Practised this week', 'accent')}
        </div>
        <div class="tiles" style="margin-top: var(--s-5)">
          ${tile(stats.total_attempts, 'Attempts')}
          ${tile(stats.total_correct, 'Correct', 'good')}
          ${tile(stats.weak_topics_count, 'Weak topics', stats.weak_topics_count ? 'bad' : '')}
          ${tile(hours((stats.total_time_minutes || 0) / 60), 'Time studied')}
        </div>
      </section>

      ${report.report_summary ? html`
        <section class="card">
          ${sectionHead('Summary')}
          <p class="muted" style="white-space: pre-wrap">${report.report_summary}</p>
        </section>` : ''}

      ${report.needs_replanning ? html`
        <button class="card card-lift" data-go="plan" style="display: block; width: 100%; text-align: left; border-color: var(--accent-line)">
          <div class="spread">
            <div class="row">
              ${icon('plan', 'icon-lg')}
              <div>
                <strong>Your plan is out of step with your results</strong>
                <p class="muted" style="font-size: var(--step--1)">The feedback agent recommends rebuilding it.</p>
              </div>
            </div>
            <span class="pill pill-accent">Replan</span>
          </div>
        </button>` : ''}

      <section>
        <div class="section-head">
          <div class="segmented" role="group" aria-label="Topic group">
            ${GROUPS.map(([id, label, field]) => html`
              <button type="button" data-group="${id}" aria-pressed="${group === id}">
                ${label} <span class="mono dim">${(report[field] || []).length}</span>
              </button>`)}
          </div>
        </div>
        ${topics.length
          ? raw(topics.map(topicCard).join(''))
          : empty({ icon: 'progress', title: 'Nothing in this group', body: 'Keep practising — topics move between groups as the evidence changes.' })}
      </section>

      ${report.recommendations?.length ? html`
        <section class="card">
          ${sectionHead('Recommendations')}
          ${report.recommendations.map((item, i) => html`
            <div class="rec"><span class="rec-n">${String(i + 1).padStart(2, '0')}</span><span>${item}</span></div>`)}
        </section>` : ''}
    </div>`;
}

function draw(host) {
  render(host, html`<div class="pane scroll">${raw(screen())}</div>`);

  $$('[data-group]', host).forEach((button) => button.addEventListener('click', () => {
    group = button.dataset.group;
    draw(host);
  }));
  $$('[data-go]', host).forEach((button) => button.addEventListener('click', () => go(button.dataset.go)));
  $$('[data-drill]', host).forEach((button) => button.addEventListener('click', () => {
    go('quiz');
    // The quiz pane mounts synchronously, so its topic field exists by now.
    queueMicrotask(() => {
      const input = document.getElementById('q-topic');
      if (input) { input.value = button.dataset.drill; input.focus(); }
    });
  }));
}

/** `payload.report` lets the tutor dock hand a report straight in. */
export async function mount(host, payload) {
  if (payload?.report?.overall_stats) set({ report: payload.report });
  draw(host);

  try {
    const report = await api.feedback.report(state.student.id);
    set({ report });
  } catch (error) {
    if (error?.status !== 404) toastErr(error);
  }
  draw(host);
}
