/**
 * Study plan — priorities first, then the calendar.
 *
 * The planner returns three things the old UI flattened into one list:
 * an ordered topic ranking, a day-by-day schedule, and milestones.
 * They answer different questions, so they get different shapes.
 */

import { html, render, raw, icon, $, $$ } from '../lib/dom.js';
import { api } from '../lib/api.js';
import { state, set } from '../lib/store.js';
import { toast, toastErr } from '../ui/toast.js';
import { empty, sectionHead, tile } from '../ui/bits.js';
import { hours, titleCase } from '../lib/format.js';

export const meta = {
  id: 'plan',
  label: 'Plan',
  icon: 'plan',
  title: 'Study plan',
  subtitle: 'Weighted toward what you get wrong',
};

let tab = 'schedule';   // 'schedule' | 'topics' | 'milestones'

const URGENCY_TONE = { high: 'bad', medium: 'warn', low: 'good' };

function form() {
  return html`
    <section class="card">
      <div class="card-head">
        <div>
          <p class="eyebrow">${state.plan ? 'Replan' : 'New plan'}</p>
          <h2>${state.plan ? 'Rebuild the schedule' : 'Lay out a schedule'}</h2>
        </div>
      </div>
      <form id="plan-form" class="stack" style="--flow: var(--s-4)">
        <div class="field-row">
          <div class="field">
            <label for="pl-days">Timeline</label>
            <select class="select" id="pl-days" name="days">
              ${[7, 14, 30, 60, 90, 180].map((n) => html`
                <option value="${n}" ${n === 30 ? 'selected' : ''}>${n} days</option>`)}
            </select>
          </div>
          <div class="field">
            <label for="pl-hours">Hours per day</label>
            <select class="select" id="pl-hours" name="hoursPerDay">
              <option value="">Let the planner decide</option>
              ${[1, 2, 3, 4, 6, 8].map((n) => html`<option value="${n}">${n} hour${n === 1 ? '' : 's'}</option>`)}
            </select>
          </div>
        </div>
        <div class="field">
          <label for="pl-focus">Focus topics <span class="dim">(optional)</span></label>
          <input class="input" id="pl-focus" name="focus" placeholder="Electrostatics, Coordinate geometry">
          <p class="field-hint">Comma separated. Left blank, the planner uses your weak areas.</p>
        </div>
        <button class="btn btn-primary" type="submit" data-submit>${icon('spark')} ${state.plan ? 'Rebuild plan' : 'Generate plan'}</button>
      </form>
    </section>`;
}

function overview(plan) {
  return html`
    <section class="card">
      <div class="card-head">
        <div>
          <p class="eyebrow">${plan.exam_type} · ${plan.timeline_days} days</p>
          <h2>The strategy</h2>
        </div>
        <span class="pill pill-accent mono">${hours(plan.total_estimated_hours)} total</span>
      </div>
      <p class="muted">${plan.explanation}</p>
      <div class="tiles" style="margin-top: var(--s-5)">
        ${tile(plan.total_topics, 'Topics')}
        ${tile(plan.daily_schedule?.length ?? 0, 'Scheduled days')}
        ${tile(plan.milestones?.length ?? 0, 'Milestones')}
        ${tile(hours((plan.total_estimated_hours || 0) / Math.max(plan.timeline_days, 1)), 'Per day, average')}
      </div>
    </section>`;
}

function scheduleTab(plan) {
  const milestoneByDay = new Map((plan.milestones || []).map((m) => [m.day, m]));
  return html`
    <div class="timeline">
      ${(plan.daily_schedule || []).map((day) => {
        const milestone = milestoneByDay.get(day.day);
        return html`
          <article class="day ${milestone ? 'milestone' : ''}">
            <div class="spread">
              <span class="day-n">Day ${day.day}${day.date ? ` · ${day.date}` : ''}</span>
              <span class="pill mono">${hours(day.hours_allocated)}</span>
            </div>
            <p style="margin-top: var(--s-2); font-weight: 600">${day.topics.join(' · ')}</p>
            ${day.focus_areas?.length ? html`
              <p class="muted" style="font-size: var(--step--1); margin-top: var(--s-1)">Focus: ${day.focus_areas.join(', ')}</p>` : ''}
            ${milestone ? html`
              <p style="font-size: var(--step--1); margin-top: var(--s-3); color: var(--accent)">
                Milestone · ${milestone.percentage}% — ${milestone.description}
              </p>` : ''}
          </article>`;
      })}
    </div>`;
}

function topicsTab(plan) {
  return html`
    <div>
      ${(plan.topics || []).map((topic) => html`
        <article class="topic-row">
          <span class="prio prio-${topic.priority}">${topic.priority}</span>
          <div>
            <div class="row-wrap">
              <strong>${topic.topic}</strong>
              <span class="pill pill-${URGENCY_TONE[topic.urgency] || 'cool'}">${titleCase(topic.urgency)} urgency</span>
              <span class="pill">${titleCase(topic.difficulty_level)}</span>
            </div>
            <p class="muted" style="font-size: var(--step--1); margin-top: var(--s-2)">${topic.reason}</p>
            ${topic.subtopics?.length ? html`
              <p class="dim" style="font-size: var(--step--1); margin-top: var(--s-1)">${topic.subtopics.join(' · ')}</p>` : ''}
          </div>
          <span class="mono muted">${hours(topic.estimated_hours)}</span>
        </article>`)}
    </div>`;
}

function milestonesTab(plan) {
  if (!plan.milestones?.length) {
    return empty({ icon: 'plan', title: 'No milestones in this plan', body: 'Longer timelines get checkpoints.' });
  }
  return html`
    <div class="timeline">
      ${plan.milestones.map((milestone) => html`
        <article class="day milestone">
          <div class="spread">
            <span class="day-n">Day ${milestone.day}</span>
            <span class="pill pill-accent mono">${milestone.percentage}%</span>
          </div>
          <p style="margin-top: var(--s-2); font-weight: 600">${milestone.description}</p>
          ${milestone.topics_covered?.length ? html`
            <p class="muted" style="font-size: var(--step--1); margin-top: var(--s-1)">${milestone.topics_covered.join(' · ')}</p>` : ''}
        </article>`)}
    </div>`;
}

function planScreen() {
  const plan = state.plan;
  const tabs = [['schedule', 'Schedule'], ['topics', 'Priorities'], ['milestones', 'Milestones']];
  const body = tab === 'topics' ? topicsTab(plan) : tab === 'milestones' ? milestonesTab(plan) : scheduleTab(plan);

  return html`
    <div class="pane-inner stack" style="--flow: var(--s-5)">
      ${raw(overview(plan))}
      <section>
        <div class="section-head">
          <div class="segmented" role="group" aria-label="Plan view">
            ${tabs.map(([id, label]) => html`
              <button type="button" data-tab="${id}" aria-pressed="${tab === id}">${label}</button>`)}
          </div>
          <button class="btn btn-quiet btn-sm" data-act="replan">Rebuild</button>
        </div>
        ${raw(body)}
      </section>
      <div id="plan-form-slot" class="hidden">${raw(form())}</div>
    </div>`;
}

async function generate(host, formEl) {
  const data = Object.fromEntries(new FormData(formEl));
  const button = $('[data-submit]', formEl);
  button.disabled = true;
  button.innerHTML = '<span class="spinner"></span> Planning…';

  try {
    const plan = await api.plan.generate({
      studentId: state.student.id,
      timelineDays: Number(data.days),
      hoursPerDay: data.hoursPerDay ? Number(data.hoursPerDay) : null,
      focusTopics: String(data.focus || '').split(',').map((t) => t.trim()).filter(Boolean),
    });
    set({ plan });
    tab = 'schedule';
    toast(`Plan ready: ${plan.total_topics} topics across ${plan.timeline_days} days.`, 'good');
    draw(host);
  } catch (error) {
    toastErr(error);
    button.disabled = false;
    button.textContent = 'Generate plan';
  }
}

function draw(host) {
  const screen = state.plan
    ? planScreen()
    : html`<div class="pane-inner stack" style="--flow: var(--s-5)">${raw(form())}</div>`;

  render(host, html`<div class="pane scroll">${raw(screen)}</div>`);

  const formEl = $('#plan-form', host);
  formEl?.addEventListener('submit', (event) => { event.preventDefault(); generate(host, formEl); });

  $$('[data-tab]', host).forEach((button) => button.addEventListener('click', () => {
    tab = button.dataset.tab;
    draw(host);
  }));

  $('[data-act="replan"]', host)?.addEventListener('click', () => {
    const slot = $('#plan-form-slot', host);
    slot.classList.toggle('hidden');
    slot.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
}

/** `payload.plan` lets the tutor dock hand a freshly generated plan in. */
export async function mount(host, payload) {
  if (payload?.plan?.daily_schedule) set({ plan: payload.plan });
  draw(host);

  if (!state.plan) {
    const plan = await api.plan.latest(state.student.id).catch(() => null);
    if (plan) { set({ plan }); draw(host); }
  }
}
