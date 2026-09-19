/**
 * A two-line event bus.
 *
 * Views need to hand work to each other — the tutor dock opens a quiz,
 * Today jumps to the card deck — without importing the shell and
 * creating a cycle. They publish here; the shell listens.
 */

const channels = new Map();

export function on(event, handler) {
  if (!channels.has(event)) channels.set(event, new Set());
  channels.get(event).add(handler);
  return () => channels.get(event)?.delete(handler);
}

export function emit(event, payload) {
  channels.get(event)?.forEach((handler) => handler(payload));
}

/** Navigate to a workspace, optionally handing it a payload. */
export const go = (view, payload) => emit('go', { view, payload });
