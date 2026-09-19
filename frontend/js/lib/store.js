/**
 * Application state.
 *
 * A single observable object plus a thin localStorage mirror for the
 * few things that should survive a reload — the old console lost your
 * identity on every refresh, which made it unusable as a study tool.
 */

const PERSIST_KEY = 'tutor.session.v1';
const THEME_KEY = 'tutor.theme';

const listeners = new Set();

export const state = {
  // identity
  student: null,          // StudentResponse
  session: null,          // SessionResponse (active tutoring session)

  // conversation
  messages: [],           // { role, content, citations, handoff, pending }
  tutorBusy: false,

  // workspaces
  quiz: null,             // QuizResponse being taken
  quizAnswers: [],        // index per question, -1 = unanswered
  quizResult: null,       // QuizResult after submit
  plan: null,             // StudyPlanResponse
  report: null,           // ProgressReportResponse
  decks: [],              // DeckResponse[]
  cardStats: null,        // flashcard stats blob
  study: null,            // { deckId, deckName, cards, index, revealed, startedAt }
  documents: [],          // document summaries
};

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Merge a patch into state and notify subscribers once. */
export function set(patch) {
  Object.assign(state, patch);
  listeners.forEach((listener) => listener(state));
  return state;
}

/* ── persistence ──────────────────────────────────────────────── */

export function persist() {
  try {
    localStorage.setItem(PERSIST_KEY, JSON.stringify({
      studentId: state.student?.id ?? null,
      sessionId: state.session?.id ?? null,
    }));
  } catch { /* private mode: stay in memory */ }
}

export function readPersisted() {
  try {
    return JSON.parse(localStorage.getItem(PERSIST_KEY) || 'null') || {};
  } catch {
    return {};
  }
}

export function clearPersisted() {
  try { localStorage.removeItem(PERSIST_KEY); } catch { /* ignore */ }
}

/* ── theme ────────────────────────────────────────────────────── */

export function readTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'light' || saved === 'dark') return saved;
  } catch { /* ignore */ }
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
  return theme;
}

export function toggleTheme() {
  return applyTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light');
}

/* ── derived helpers ──────────────────────────────────────────── */

export const isSignedIn = () => Boolean(state.student);
export const hasLiveSession = () => Boolean(state.session?.is_active);
export const dueCardCount = () => state.decks.reduce((total, deck) => total + (deck.due_count || 0), 0);
