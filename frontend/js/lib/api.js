/**
 * REST client for the Agentic AI Tutor API.
 *
 * Every endpoint the console uses is named here, so the surface the UI
 * depends on is one file long and easy to diff against the backend.
 *
 * Base URL resolution, in order:
 *   1. ?api=<url> in the address bar, or a previously remembered one
 *   2. same origin, when the page is served by the API itself
 *   3. http://127.0.0.1:8000/api, for opening index.html off disk
 *
 * The override is deliberately restricted to the page's own origin or a
 * loopback address. Every request carries the student's credentials —
 * the password on login, the bearer token after — so an unrestricted
 * `?api=` would turn a link like `/app/?api=https://elsewhere/api` into
 * a credential-exfiltration primitive, and a remembered one would keep
 * exfiltrating long after the link was clicked.
 */

const OVERRIDE_KEY = 'tutor.apiBase';
const TOKEN_KEY = 'tutor.token';

const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]', '::1']);

const sameOriginDefault = () =>
  (location.protocol === 'http:' || location.protocol === 'https:')
    ? `${location.origin}/api`
    : 'http://127.0.0.1:8000/api';

/** Return a trimmed base URL if it is somewhere we are willing to send credentials. */
function acceptableBase(candidate) {
  let url;
  try {
    url = new URL(candidate, location.href);
  } catch {
    return null;
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
  if (url.origin !== location.origin && !LOOPBACK_HOSTS.has(url.hostname)) return null;
  return `${url.origin}${url.pathname}`.replace(/\/$/, '');
}

function resolveBase() {
  const requested = new URLSearchParams(location.search).get('api');

  if (requested) {
    const accepted = acceptableBase(requested);
    if (!accepted) {
      console.warn(`Ignoring ?api=${requested}: only this origin or a loopback address is allowed.`);
      try { localStorage.removeItem(OVERRIDE_KEY); } catch { /* private mode */ }
      return sameOriginDefault();
    }
    try { localStorage.setItem(OVERRIDE_KEY, accepted); } catch { /* private mode */ }
    return accepted;
  }

  let saved = null;
  try { saved = localStorage.getItem(OVERRIDE_KEY); } catch { /* private mode */ }
  if (saved) {
    // Re-check on every load: what was acceptable when it was stored may
    // not be now, and storage is writable by anything running on the page.
    const accepted = acceptableBase(saved);
    if (accepted) return accepted;
    try { localStorage.removeItem(OVERRIDE_KEY); } catch { /* private mode */ }
  }

  return sameOriginDefault();
}

export const API_BASE = resolveBase();

/** The API root, one level above the `/api` prefix — where /health lives. */
export const API_ROOT = API_BASE.replace(/\/api$/, '') || API_BASE;

/* ── bearer token ─────────────────────────────────────────────
   Every student data endpoint requires one. Register and login both
   return `access_token` alongside the profile fields; it is kept here,
   sent on every request, and dropped on a 401 so a stale token bounces
   back to sign-in rather than wedging the console.
   ──────────────────────────────────────────────────────────────── */

let authToken = (() => {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
})();

let onUnauthorized = null;

export function setAuthToken(token) {
  authToken = token || null;
  try {
    if (authToken) localStorage.setItem(TOKEN_KEY, authToken);
    else localStorage.removeItem(TOKEN_KEY);
  } catch { /* private mode */ }
}

export const getAuthToken = () => authToken;

/** Called once by the shell so a stale token can bounce back to sign-in. */
export const setUnauthorizedHandler = (handler) => { onUnauthorized = handler; };

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

/** FastAPI reports errors as `detail`, and validation errors as a list. */
function readError(payload, status) {
  if (!payload) return `Request failed (${status})`;
  const { detail, message } = payload;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : '';
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .filter(Boolean)
      .join('; ') || `Request failed (${status})`;
  }
  if (typeof message === 'string') return message;
  return `Request failed (${status})`;
}

async function request(path, { method = 'GET', body, form, signal } = {}) {
  const init = { method, signal, headers: {} };
  if (authToken) init.headers.Authorization = `Bearer ${authToken}`;

  if (form) {
    init.body = form;              // let the browser set the multipart boundary
  } else if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (cause) {
    if (cause?.name === 'AbortError') throw cause;
    throw new ApiError(
      `Cannot reach the API at ${API_BASE}. Is the server running?`,
      0,
      { cause: String(cause) },
    );
  }

  const isJson = (response.headers.get('content-type') || '').includes('application/json');
  const payload = isJson ? await response.json().catch(() => null) : null;

  if (!response.ok) {
    if (response.status === 401 && authToken) {
      setAuthToken(null);
      onUnauthorized?.();
    }
    throw new ApiError(readError(payload, response.status), response.status, payload);
  }
  return payload;
}

const qs = (params) => {
  const search = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null),
  ).toString();
  return search ? `?${search}` : '';
};

export const api = {
  health: () => fetch(`${API_ROOT}/health`).then((r) => (r.ok ? r.json() : Promise.reject(new ApiError('Health check failed', r.status)))),

  students: {
    register: (data) => request('/students/register', { method: 'POST', body: data }),
    login: (email, password) => request('/students/login', { method: 'POST', body: { email, password } }),
    get: (studentId) => request(`/students/${encodeURIComponent(studentId)}`),
  },

  sessions: {
    start: (studentId, sessionType = 'general') =>
      request('/sessions/start', { method: 'POST', body: { student_id: studentId, session_type: sessionType } }),
    get: (sessionId) => request(`/sessions/${encodeURIComponent(sessionId)}`),
    end: (sessionId) => request(`/sessions/${encodeURIComponent(sessionId)}/end`, { method: 'POST' }),
    listFor: (studentId) => request(`/sessions${qs({ student_id: studentId })}`),
    messages: (sessionId) => request(`/sessions/${encodeURIComponent(sessionId)}/messages`),
  },

  chat: {
    send: (sessionId, message, intent = null) =>
      request('/chat', { method: 'POST', body: { session_id: sessionId, message, intent } }),
  },

  quiz: {
    generate: ({ studentId, topic, difficulty, numQuestions }) =>
      request('/quiz/generate', {
        method: 'POST',
        body: {
          student_id: studentId,
          topic,
          difficulty: difficulty || null,
          num_questions: numQuestions,
        },
      }),
    submit: ({ quizId, studentId, answers }) =>
      request('/quiz/submit', {
        method: 'POST',
        body: { quiz_id: quizId, student_id: studentId, answers },
      }),
  },

  plan: {
    generate: ({ studentId, timelineDays, focusTopics, hoursPerDay }) =>
      request('/plan/generate', {
        method: 'POST',
        body: {
          student_id: studentId,
          timeline_days: timelineDays,
          focus_topics: focusTopics?.length ? focusTopics : null,
          hours_per_day: hoursPerDay || null,
        },
      }),
    latest: (studentId) => request(`/plan/${encodeURIComponent(studentId)}`),
  },

  feedback: {
    report: (studentId, reportType = 'student') =>
      request(`/feedback/${encodeURIComponent(studentId)}${qs({ report_type: reportType })}`),
  },

  documents: {
    upload: ({ file, studentId, subject }) => {
      const form = new FormData();
      form.append('file', file);
      form.append('student_id', studentId);
      if (subject) form.append('subject', subject);
      return request('/documents/upload', { method: 'POST', form });
    },
    list: (studentId) => request(`/documents/list/${encodeURIComponent(studentId)}`),
  },

  flashcards: {
    generate: (studentId, { topic, numCards, difficulty, useDocuments }) =>
      request(`/flashcards/generate/${encodeURIComponent(studentId)}`, {
        method: 'POST',
        body: {
          topic,
          num_cards: numCards,
          difficulty,
          use_documents: useDocuments,
        },
      }),
    decks: (studentId) => request(`/flashcards/decks/${encodeURIComponent(studentId)}`),
    deck: (deckId) => request(`/flashcards/deck/${encodeURIComponent(deckId)}`),
    study: (deckId, { maxCards = 20, includeNew = true } = {}) =>
      request(`/flashcards/study/${encodeURIComponent(deckId)}${qs({ max_cards: maxCards, include_new: includeNew })}`),
    reveal: (cardId) => request(`/flashcards/card/${encodeURIComponent(cardId)}/reveal`),
    review: ({ cardId, quality, responseTimeMs }) =>
      request('/flashcards/review', {
        method: 'POST',
        body: { card_id: cardId, quality, response_time_ms: responseTimeMs ?? null },
      }),
    deleteDeck: (deckId) => request(`/flashcards/deck/${encodeURIComponent(deckId)}`, { method: 'DELETE' }),
    stats: (studentId) => request(`/flashcards/stats/${encodeURIComponent(studentId)}`),
  },
};
