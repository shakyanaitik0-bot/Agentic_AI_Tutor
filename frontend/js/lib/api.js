/**
 * REST client for the Agentic AI Tutor API.
 *
 * Every endpoint the console uses is named here, so the surface the UI
 * depends on is one file long and easy to diff against the backend.
 *
 * Base URL resolution, in order:
 *   1. ?api=<url> in the address bar (handy when the API is remote)
 *   2. a previously remembered override
 *   3. same origin, when the page is served by the API itself
 *   4. http://127.0.0.1:8000/api, for opening index.html off disk
 */

const OVERRIDE_KEY = 'tutor.apiBase';
const TOKEN_KEY = 'tutor.token';

function resolveBase() {
  const fromQuery = new URLSearchParams(location.search).get('api');
  if (fromQuery) {
    try { localStorage.setItem(OVERRIDE_KEY, fromQuery); } catch { /* private mode */ }
    return fromQuery.replace(/\/$/, '');
  }
  try {
    const saved = localStorage.getItem(OVERRIDE_KEY);
    if (saved) return saved.replace(/\/$/, '');
  } catch { /* private mode */ }

  if (location.protocol === 'http:' || location.protocol === 'https:') {
    return `${location.origin}/api`;
  }
  return 'http://127.0.0.1:8000/api';
}

export const API_BASE = resolveBase();

/** The API root, one level above the `/api` prefix — where /health lives. */
export const API_ROOT = API_BASE.replace(/\/api$/, '') || API_BASE;

/* ── bearer token ─────────────────────────────────────────────
   Login does not issue a JWT yet, but the machinery to require one
   exists server-side. Reading `access_token` off the login response
   and sending it back costs nothing today and means the console keeps
   working the day the backend starts demanding it.
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
