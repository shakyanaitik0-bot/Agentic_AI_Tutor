/**
 * Session lifecycle.
 *
 * The backend requires an *active* session before `/chat` will answer,
 * so the console opens one on sign-in and quietly reopens it if the
 * stored one has been ended. Nothing in the UI should ever ask the user
 * to "start a session" before they can type a question.
 */

import { api } from './api.js';
import { state, set, persist } from './store.js';
import { toast } from '../ui/toast.js';

export async function startSession(sessionType = 'general') {
  const session = await api.sessions.start(state.student.id, sessionType);
  set({ session });
  persist();
  return session;
}

export async function endSession() {
  if (!state.session) return null;
  const session = await api.sessions.end(state.session.id);
  set({ session, messages: [] });
  persist();
  toast('Session closed. Your progress is saved.', 'good');
  return session;
}

/** Return a live session, opening one if the current one is missing or closed. */
export async function ensureSession() {
  if (state.session?.is_active) return state.session;
  return startSession();
}

/**
 * On sign-in: adopt the most recent active session if the server still
 * has one, replaying its transcript, otherwise open a fresh one.
 */
export async function restoreOrStart(preferredSessionId = null) {
  let session = null;

  if (preferredSessionId) {
    session = await api.sessions.get(preferredSessionId).catch(() => null);
    if (session && !session.is_active) session = null;
  }

  if (!session) {
    const sessions = await api.sessions.listFor(state.student.id).catch(() => []);
    session = (sessions || []).find((item) => item.is_active) || null;
  }

  if (!session) {
    set({ messages: [] });
    return startSession();
  }

  set({ session });
  persist();
  await replayMessages(session.id);
  return session;
}

/** Turn stored Message rows back into dock bubbles. */
export async function replayMessages(sessionId) {
  const rows = await api.sessions.messages(sessionId).catch(() => []);
  const messages = (rows || []).map((row) => {
    if (row.role === 'user') return { role: 'user', content: row.content };
    const meta = row.message_metadata || {};
    return {
      role: 'tutor',
      content: readableAnswer(meta) ?? row.content,
      citations: meta.citations || [],
      handoff: handoffFor(meta),
    };
  });
  set({ messages });
  return messages;
}

/**
 * `/api/chat` returns an untyped dict whose shape depends on which agent
 * ran. Rather than sniffing keys at every call site, both the answer
 * text and the "there is a richer artifact behind this" hand-off are
 * read here, once.
 */
export function readableAnswer(agentResponse) {
  if (!agentResponse || typeof agentResponse !== 'object') return null;
  const { response, message, error, report_summary: summary, explanation } = agentResponse;
  return response || message || summary || explanation || error || null;
}

export function handoffFor(agentResponse) {
  if (!agentResponse || typeof agentResponse !== 'object') return null;

  const quiz = agentResponse.quiz;
  if (quiz?.questions?.length) {
    return { kind: 'quiz', payload: quiz, label: 'Open this quiz', sub: `${quiz.questions.length} questions on ${quiz.topic}` };
  }

  const plan = agentResponse.study_plan || agentResponse.plan;
  if (plan?.daily_schedule) {
    return { kind: 'plan', payload: plan, label: 'Open this study plan', sub: `${plan.timeline_days} days · ${plan.total_topics} topics` };
  }

  const report = agentResponse.data || agentResponse.feedback || agentResponse.report;
  if (report?.overall_stats) {
    return { kind: 'progress', payload: report, label: 'Open the full report', sub: 'Topic-by-topic breakdown' };
  }

  return null;
}
