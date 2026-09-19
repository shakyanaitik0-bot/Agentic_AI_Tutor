/**
 * Quiz — one question at a time, answerable without the mouse.
 *
 * The old console rendered all questions as a long form and graded the
 * lot at the end. Here the question owns the screen, 1–4 picks an
 * answer, Enter moves on, and the review afterwards is where the
 * explanations live.
 */

import { html, render, raw, icon, $, $$ } from '../lib/dom.js';
import { api } from '../lib/api.js';
import { state, set } from '../lib/store.js';
import { toastErr, toast } from '../ui/toast.js';
import { ring, sectionHead } from '../ui/bits.js';
import { accuracyTone, titleCase } from '../lib/format.js';

export const meta = {
  id: 'quiz',
  label: 'Quiz',
  icon: 'quiz',
  title: 'Quiz',
  subtitle: 'Adaptive multiple choice',
};

const LETTERS = ['A', 'B', 'C', 'D'];
const DIFFICULTIES = ['adaptive', 'easy', 'medium', 'hard'];

let cursor = 0;          // index of the question on screen
let keyHandler = null;   // so the shell can unbind on leave

/* ── setup ────────────────────────────────────────────────────── */

function setupScreen() {
  const suggested = state.report?.weak_topics?.slice(0, 4).map((topic) => topic.topic)
    || state.student?.weak_areas?.slice(0, 4)
    || [];

  return html`
    <div class="pane-inner stack" style="--flow: var(--s-5)">
      <section class="card">
        <div class="card-head">
          <div>
            <p class="eyebrow">New quiz</p>
            <h2>What are we testing?</h2>
          </div>
        </div>

        <form id="quiz-setup" class="stack" style="--flow: var(--s-4)">
          <div class="field">
            <label for="q-topic">Topic</label>
            <input class="input" id="q-topic" name="topic" required minlength="2" maxlength="100"
                   placeholder="Rotational motion, Integration by parts, Redox reactions…">
            ${suggested.length ? html`
              <div class="row-wrap" style="margin-top: var(--s-2)">
                <span class="field-hint">Weak right now:</span>
                ${suggested.map((topic) => html`
                  <button class="pill" type="button" data-topic="${topic}">${topic}</button>`)}
              </div>` : ''}
          </div>

          <div class="field-row">
            <div class="field">
              <label for="q-count">Questions</label>
              <select class="select" id="q-count" name="num">
                ${[3, 5, 8, 10].map((n) => html`<option value="${n}" ${n === 5 ? 'selected' : ''}>${n}</option>`)}
              </select>
            </div>
            <div class="field">
              <label for="q-diff">Difficulty</label>
              <select class="select" id="q-diff" name="difficulty">
                ${DIFFICULTIES.map((level) => html`<option value="${level}">${titleCase(level)}</option>`)}
              </select>
              <p class="field-hint">Adaptive follows your recent accuracy.</p>
            </div>
          </div>

          <button class="btn btn-primary btn-lg" type="submit" data-submit>${icon('spark')} Generate quiz</button>
        </form>
      </section>

      ${state.quizResult ? raw(lastResultCard()) : ''}
    </div>`;
}

function lastResultCard() {
  const result = state.quizResult;
  return html`
    <section class="card">
      ${sectionHead('Last attempt')}
      <div class="spread">
        <div>
          <div class="tile-value" style="color: var(--${accuracyTone(result.accuracy)})">${Math.round(result.accuracy)}%</div>
          <p class="muted">${result.correct_answers} of ${result.total_questions} correct</p>
        </div>
        <button class="btn btn-ghost btn-sm" data-act="review-last">See the review</button>
      </div>
    </section>`;
}

/* ── runner ───────────────────────────────────────────────────── */

function runnerScreen() {
  const quiz = state.quiz;
  const question = quiz.questions[cursor];
  const chosen = state.quizAnswers[cursor];
  const answered = state.quizAnswers.filter((answer) => answer >= 0).length;
  const isLast = cursor === quiz.questions.length - 1;

  return html`
    <div class="pane-inner">
      <div class="quiz-head">
        <div class="spread">
          <div class="row-wrap">
            <span class="pill pill-accent">${quiz.topic}</span>
            <span class="pill">${titleCase(quiz.difficulty)}</span>
          </div>
          <span class="quiz-count">${cursor + 1} / ${quiz.questions.length}</span>
        </div>
        <div class="bar"><i style="width: ${((cursor + 1) / quiz.questions.length) * 100}%"></i></div>
      </div>

      <h2 class="quiz-q">${question.question_text}</h2>

      <div class="choices">
        ${question.options.map((option, i) => html`
          <button class="choice" type="button" data-choose="${i}" aria-pressed="${chosen === i}">
            <span class="choice-key">${LETTERS[i]}</span>
            <span>${option}</span>
            ${chosen === i ? icon('check') : raw('<span></span>')}
          </button>`)}
      </div>

      <div class="spread" style="margin-top: var(--s-6)">
        <button class="btn btn-quiet" data-act="prev" ${cursor === 0 ? 'disabled' : ''}>Back</button>
        <span class="quiz-count">${answered} answered · keys 1–4, Enter to continue</span>
        ${isLast
          ? html`<button class="btn btn-primary" data-act="submit" ${answered < quiz.questions.length ? 'disabled' : ''}>Submit quiz</button>`
          : html`<button class="btn btn-primary" data-act="next" ${chosen === undefined || chosen < 0 ? 'disabled' : ''}>Next</button>`}
      </div>

      <button class="btn btn-quiet btn-sm" data-act="abandon" style="margin-top: var(--s-5)">Discard this quiz</button>
    </div>`;
}

/* ── results ──────────────────────────────────────────────────── */

function resultScreen() {
  const result = state.quizResult;
  const quiz = state.quiz;
  const tone = accuracyTone(result.accuracy);

  return html`
    <div class="pane-inner stack" style="--flow: var(--s-5)">
      <section class="card">
        <div class="score-hero">
          ${ring(result.accuracy, result.passed ? 'Passed' : 'Keep going', tone)}
          <div>
            <p class="score-num" style="color: var(--${tone})">${result.correct_answers}<span class="dim">/${result.total_questions}</span></p>
            <p class="muted">${quiz ? `on ${quiz.topic}` : ''}</p>
          </div>
          <div class="row-wrap" style="justify-content: center">
            <button class="btn btn-primary" data-act="again">Another quiz on this topic</button>
            <button class="btn btn-ghost" data-act="new">Pick a new topic</button>
          </div>
        </div>
      </section>

      <section>
        ${sectionHead('Review')}
        ${result.results.map((item, i) => raw(reviewItem(item, i)))}
      </section>
    </div>`;
}

function reviewItem(item, index) {
  const question = state.quiz?.questions?.[index];
  const options = question?.options || [];
  return html`
    <article class="review-item">
      <div class="row" style="align-items: flex-start; gap: var(--s-3)">
        <span class="pill ${item.is_correct ? 'pill-good' : 'pill-bad'}">${item.is_correct ? 'Correct' : 'Missed'}</span>
        <div class="grow">
          <p style="font-weight: 600">${index + 1}. ${question?.question_text || item.question_id}</p>
          <p class="muted" style="font-size: var(--step--1); margin-top: var(--s-2)">
            You chose <b>${LETTERS[item.selected_answer] ?? '—'}</b>${options[item.selected_answer] ? ` · ${options[item.selected_answer]}` : ''}
            ${item.is_correct ? '' : html`<br>Answer is <b>${LETTERS[item.correct_answer]}</b>${options[item.correct_answer] ? ` · ${options[item.correct_answer]}` : ''}`}
          </p>
          ${item.explanation ? html`<div class="explain">${item.explanation}</div>` : ''}
        </div>
      </div>
    </article>`;
}

/* ── behaviour ────────────────────────────────────────────────── */

function choose(index) {
  const answers = state.quizAnswers.slice();
  answers[cursor] = index;
  set({ quizAnswers: answers });
}

async function submit(host) {
  const button = $('[data-act="submit"]', host);
  if (button) { button.disabled = true; button.innerHTML = '<span class="spinner"></span> Grading…'; }
  try {
    const result = await api.quiz.submit({
      quizId: state.quiz.quiz_id,
      studentId: state.student.id,
      answers: state.quizAnswers,
    });
    set({ quizResult: result });
    toast(result.passed ? 'Passed. Weak-topic scores updated.' : 'Graded. The misses are now weighted in your plan.', result.passed ? 'good' : 'info');
    draw(host);
  } catch (error) {
    toastErr(error);
    if (button) { button.disabled = false; button.textContent = 'Submit quiz'; }
  }
}

async function generate(host, form) {
  const data = Object.fromEntries(new FormData(form));
  if (!data.topic || String(data.topic).trim().length < 2) {
    return toastErr(new Error('Give the quiz a topic first.'));
  }

  const button = $('[data-submit]', form);
  button.disabled = true;
  button.innerHTML = '<span class="spinner"></span> Writing questions…';

  try {
    const quiz = await api.quiz.generate({
      studentId: state.student.id,
      topic: String(data.topic).trim(),
      difficulty: data.difficulty === 'adaptive' ? null : data.difficulty,
      numQuestions: Number(data.num),
    });
    cursor = 0;
    set({ quiz, quizAnswers: new Array(quiz.questions.length).fill(-1), quizResult: null });
    draw(host);
  } catch (error) {
    toastErr(error);
    button.disabled = false;
    button.textContent = 'Generate quiz';
  }
}

function bindKeys(host) {
  unbindKeys();
  keyHandler = (event) => {
    if (!state.quiz || state.quizResult) return;
    if (event.target.matches('input, textarea, select')) return;

    const digit = Number(event.key);
    if (digit >= 1 && digit <= 4 && state.quiz.questions[cursor].options[digit - 1] !== undefined) {
      event.preventDefault();
      choose(digit - 1);
      draw(host);
      return;
    }
    if (event.key === 'Enter' || event.key === 'ArrowRight') {
      const last = cursor === state.quiz.questions.length - 1;
      if (last) { if (state.quizAnswers.every((a) => a >= 0)) submit(host); return; }
      if (state.quizAnswers[cursor] >= 0) { cursor += 1; draw(host); }
    }
    if (event.key === 'ArrowLeft' && cursor > 0) { cursor -= 1; draw(host); }
  };
  window.addEventListener('keydown', keyHandler);
}

function unbindKeys() {
  if (keyHandler) window.removeEventListener('keydown', keyHandler);
  keyHandler = null;
}

function draw(host) {
  const screen = state.quizResult ? resultScreen() : state.quiz ? runnerScreen() : setupScreen();
  render(host, html`<div class="pane scroll">${raw(screen)}</div>`);

  if (state.quiz && !state.quizResult) bindKeys(host); else unbindKeys();

  const form = $('#quiz-setup', host);
  form?.addEventListener('submit', (event) => { event.preventDefault(); generate(host, form); });
  $$('[data-topic]', host).forEach((chip) => chip.addEventListener('click', () => {
    $('#q-topic', host).value = chip.dataset.topic;
  }));

  $$('[data-choose]', host).forEach((choice) => choice.addEventListener('click', () => {
    choose(Number(choice.dataset.choose));
    draw(host);
  }));

  const act = (name, handler) => $(`[data-act="${name}"]`, host)?.addEventListener('click', handler);

  act('next', () => { cursor = Math.min(cursor + 1, state.quiz.questions.length - 1); draw(host); });
  act('prev', () => { cursor = Math.max(cursor - 1, 0); draw(host); });
  act('submit', () => submit(host));
  act('abandon', () => { set({ quiz: null, quizAnswers: [], quizResult: null }); draw(host); });
  act('review-last', () => draw(host));
  act('new', () => { set({ quiz: null, quizAnswers: [], quizResult: null }); draw(host); });
  act('again', () => {
    const topic = state.quiz?.topic;
    set({ quiz: null, quizAnswers: [], quizResult: null });
    draw(host);
    if (topic) $('#q-topic', host).value = topic;
  });
}

/** `payload.quiz` lets the tutor dock hand a generated quiz straight in. */
export function mount(host, payload) {
  if (payload?.quiz?.questions?.length) {
    cursor = 0;
    set({ quiz: payload.quiz, quizAnswers: new Array(payload.quiz.questions.length).fill(-1), quizResult: null });
  }
  draw(host);
}

export function unmount() {
  unbindKeys();
}
