/**
 * Tiny DOM layer.
 *
 * The rule it enforces: server-supplied strings (question text, citation
 * titles, filenames, LLM prose) are escaped on their way into markup.
 *
 * `html` is the only sanctioned way to build markup. It returns a
 * `Markup` value rather than a string, so nested templates compose
 * without double-escaping while anything else interpolated — a plain
 * string from an API response — is escaped. `raw()` is the deliberate,
 * greppable opt-out.
 */

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ESCAPES[ch]);
}

/** Markup that is already safe. `toString` keeps `[].join('')` working. */
class Markup {
  constructor(value) { this.value = value; }
  toString() { return this.value; }
}

/** Mark a string as already-safe markup. */
export const raw = (markup) => (markup instanceof Markup ? markup : new Markup(String(markup ?? '')));

export const isMarkup = (value) => value instanceof Markup;

function interpolate(value) {
  if (value == null || value === false) return '';
  if (value instanceof Markup) return value.value;
  if (Array.isArray(value)) return value.map(interpolate).join('');
  return escapeHtml(value);
}

/** Tagged template that escapes every interpolation it is not told to trust. */
export function html(strings, ...values) {
  let out = strings[0];
  for (let i = 0; i < values.length; i += 1) out += interpolate(values[i]) + strings[i + 1];
  return new Markup(out);
}

/** Build a detached element tree from markup. */
export function fragment(markup) {
  const template = document.createElement('template');
  template.innerHTML = String(markup).trim();
  return template.content;
}

/** Replace a host element's children with freshly parsed markup. */
export function render(host, markup) {
  host.replaceChildren(fragment(markup));
  return host;
}

export const $ = (selector, scope = document) => scope.querySelector(selector);
export const $$ = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));

/** `<svg><use href="#i-quiz"/></svg>` without the ceremony. */
export function icon(name, cls = '') {
  return raw(`<svg class="${escapeHtml(cls)}" aria-hidden="true"><use href="#i-${escapeHtml(name)}"/></svg>`);
}

/**
 * Delegated events, scoped to a host so a re-render never leaves
 * listeners behind on detached nodes.
 */
export function on(host, type, selector, handler) {
  host.addEventListener(type, (event) => {
    const match = event.target.closest(selector);
    if (match && host.contains(match)) handler(event, match);
  });
}
