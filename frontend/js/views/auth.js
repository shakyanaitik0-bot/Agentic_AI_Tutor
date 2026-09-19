/**
 * Sign-in / sign-up.
 *
 * Takes the whole viewport rather than hiding behind the shell: it is a
 * doorway, not a workspace. The left panel states what the thing is,
 * the right panel is the shortest form that will do.
 */

import { html, render, raw, icon, $, escapeHtml } from '../lib/dom.js';
import { api } from '../lib/api.js';
import { toastErr } from '../ui/toast.js';

const EXAM_TYPES = ['JEE', 'SAT', 'GRE'];

const POINTS = [
  ['spark', 'A tutor that stays beside you', 'Ask a question mid-quiz without losing the question.'],
  ['cards', 'Cards that know when to come back', 'SM-2 scheduling, graded with the number keys.'],
  ['progress', 'Difficulty that follows the evidence', 'Quizzes re-aim at whatever the data says is weak.'],
];

const splitList = (value) =>
  String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

function panel() {
  return html`
    <aside class="auth-art">
      <div class="row">
        <span class="rail-mark">AT</span>
        <strong>Agentic AI Tutor</strong>
      </div>

      <div class="stack" style="--flow: var(--s-6)">
        <h1 class="auth-claim">Study with something that <em>answers back</em>.</h1>
        <ul class="auth-points">
          ${POINTS.map(([name, title, body]) => html`
            <li class="auth-point">
              ${icon(name)}
              <span><strong>${title}</strong><span>${body}</span></span>
            </li>`)}
        </ul>
      </div>

      <p class="dim" style="font-size: var(--step--1)">
        Five agents behind one console: planner, quiz, feedback, flashcards and conversation.
      </p>
    </aside>`;
}

function loginForm() {
  return html`
    <form class="auth-form stack" id="form-login" novalidate>
      <div>
        <p class="eyebrow">Welcome back</p>
        <h2>Sign in</h2>
      </div>

      <div class="field">
        <label for="li-email">Email</label>
        <input class="input" id="li-email" name="email" type="email" autocomplete="email" required placeholder="you@example.com">
      </div>

      <div class="field">
        <label for="li-password">Password</label>
        <input class="input" id="li-password" name="password" type="password" autocomplete="current-password" required placeholder="••••••••">
      </div>

      <button class="btn btn-primary btn-block btn-lg" type="submit" data-submit>Sign in</button>
      <p class="muted" style="font-size: var(--step--1)">
        No account yet? <button class="btn-quiet" type="button" data-go="register" style="color: var(--cool); padding: 0">Create one</button>
      </p>
    </form>`;
}

function registerForm() {
  return html`
    <form class="auth-form stack" id="form-register" novalidate>
      <div>
        <p class="eyebrow">First time</p>
        <h2>Create an account</h2>
      </div>

      <div class="field">
        <label for="rg-name">Name</label>
        <input class="input" id="rg-name" name="name" required minlength="2" placeholder="Your name">
      </div>

      <div class="field">
        <label for="rg-email">Email</label>
        <input class="input" id="rg-email" name="email" type="email" autocomplete="email" required placeholder="you@example.com">
      </div>

      <div class="field">
        <label for="rg-password">Password</label>
        <input class="input" id="rg-password" name="password" type="password" autocomplete="new-password" required minlength="6" placeholder="At least 6 characters">
      </div>

      <div class="field">
        <label for="rg-exam">Preparing for</label>
        <select class="select" id="rg-exam" name="exam_type">
          ${EXAM_TYPES.map((exam) => html`<option value="${exam}">${exam}</option>`)}
        </select>
      </div>

      <div class="field">
        <label for="rg-weak">Topics you find hard <span class="dim">(optional)</span></label>
        <input class="input" id="rg-weak" name="weak" placeholder="Thermodynamics, Probability">
        <p class="field-hint">Comma separated. The planner weights these first.</p>
      </div>

      <div class="field">
        <label for="rg-strong">Topics you are solid on <span class="dim">(optional)</span></label>
        <input class="input" id="rg-strong" name="strong" placeholder="Algebra, Kinematics">
      </div>

      <button class="btn btn-primary btn-block btn-lg" type="submit" data-submit>Create account</button>
      <p class="muted" style="font-size: var(--step--1)">
        Already registered? <button class="btn-quiet" type="button" data-go="login" style="color: var(--cool); padding: 0">Sign in</button>
      </p>
    </form>`;
}

/** Swap a submit button into a spinner while a request is in flight. */
function busy(form, isBusy, label) {
  const button = $('[data-submit]', form);
  if (!button) return;
  button.disabled = isBusy;
  button.innerHTML = isBusy
    ? '<span class="spinner"></span> Working…'
    : escapeHtml(label);
}

/**
 * @param {HTMLElement} host
 * @param {(student: object) => void} onSignedIn
 */
export function mountAuth(host, onSignedIn) {
  let mode = 'login';

  const draw = () => {
    render(host, html`
      <div class="auth">
        ${raw(panel())}
        <div class="auth-form-wrap">${raw(mode === 'login' ? loginForm() : registerForm())}</div>
      </div>`);
    wire();
  };

  function wire() {
    host.querySelectorAll('[data-go]').forEach((button) => {
      button.addEventListener('click', () => {
        mode = button.dataset.go;
        draw();
      });
    });

    const form = $('form', host);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form));

      if (mode === 'login') {
        if (!data.email || !data.password) return toastErr(new Error('Email and password are required.'));
        busy(form, true);
        try {
          onSignedIn(await api.students.login(data.email, data.password));
        } catch (error) {
          toastErr(error);
          busy(form, false, 'Sign in');
        }
        return;
      }

      if (!data.name || !data.email || !data.password) {
        return toastErr(new Error('Name, email and password are required.'));
      }
      if (String(data.password).length < 6) {
        return toastErr(new Error('Password must be at least 6 characters.'));
      }

      busy(form, true);
      try {
        onSignedIn(await api.students.register({
          name: data.name,
          email: data.email,
          password: data.password,
          exam_type: data.exam_type,
          weak_areas: splitList(data.weak),
          strong_areas: splitList(data.strong),
        }));
      } catch (error) {
        toastErr(error);
        busy(form, false, 'Create account');
      }
    });

    $('input', host)?.focus();
  }

  draw();
}
