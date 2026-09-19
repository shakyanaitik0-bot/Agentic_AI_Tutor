/** Display formatting. Kept in one place so units read the same everywhere. */

export const pct = (n) => `${Math.round(Number(n) || 0)}%`;

export const round1 = (n) => (Math.round((Number(n) || 0) * 10) / 10).toString();

export function hours(n) {
  const value = Number(n) || 0;
  return value >= 10 ? `${Math.round(value)}h` : `${round1(value)}h`;
}

export function shortDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function timeOfDay(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

export function relativeDays(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const days = Math.round((date - new Date()) / 86_400_000);
  if (days === 0) return 'today';
  if (days === 1) return 'tomorrow';
  if (days === -1) return 'yesterday';
  return days > 0 ? `in ${days} days` : `${Math.abs(days)} days ago`;
}

export function greeting(now = new Date()) {
  const hour = now.getHours();
  if (hour < 5) return 'Still up';
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

/** Accuracy → the token family used to colour it. */
export function accuracyTone(accuracy) {
  const value = Number(accuracy) || 0;
  if (value >= 80) return 'good';
  if (value >= 50) return 'warn';
  return 'bad';
}

export function titleCase(value) {
  return String(value ?? '')
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (ch) => ch.toUpperCase());
}
