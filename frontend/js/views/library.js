/**
 * Library — the documents that ground the tutor's answers.
 *
 * Upload is a drop target rather than a file input in a form: it is the
 * only thing this pane does, so it may as well be the whole pane.
 */

import { html, render, raw, icon, $, $$ } from '../lib/dom.js';
import { api } from '../lib/api.js';
import { state, set } from '../lib/store.js';
import { toast, toastErr } from '../ui/toast.js';
import { empty, sectionHead, tile } from '../ui/bits.js';
import { shortDate } from '../lib/format.js';

export const meta = {
  id: 'library',
  label: 'Library',
  icon: 'library',
  title: 'Library',
  subtitle: 'Your material, used as context',
};

const ACCEPT = '.pdf,.txt,.docx,.doc,.md';
const MAX_MB = 25;

let uploading = false;

function screen() {
  const docs = state.documents;
  const chunks = docs.reduce((total, doc) => total + (doc.num_chunks || 0), 0);

  return html`
    <div class="pane-inner stack" style="--flow: var(--s-5)">
      <section class="card">
        <div class="card-head">
          <div>
            <p class="eyebrow">Upload</p>
            <h2>Add study material</h2>
          </div>
        </div>

        <div class="field" style="margin-bottom: var(--s-4)">
          <label for="doc-subject">Subject <span class="dim">(optional)</span></label>
          <input class="input" id="doc-subject" placeholder="Physics, Organic chemistry…">
          <p class="field-hint">Tagging helps retrieval pick the right chunks later.</p>
        </div>

        <div class="drop" id="drop" role="button" tabindex="0" aria-label="Choose a file to upload">
          ${uploading
            ? html`<span class="spinner" style="font-size: 1.6rem"></span><strong>Chunking and embedding…</strong>
                   <p class="muted" style="font-size: var(--step--1)">Large PDFs take a moment.</p>`
            : html`${icon('upload')}
                   <strong>Drop a file here, or click to choose</strong>
                   <p class="muted" style="font-size: var(--step--1)">PDF, DOCX, TXT or Markdown · up to ${MAX_MB} MB</p>`}
        </div>
        <input type="file" id="doc-file" accept="${ACCEPT}" class="sr-only">
      </section>

      ${docs.length ? html`
        <div class="tiles">
          ${tile(docs.length, 'Documents')}
          ${tile(chunks, 'Indexed chunks')}
        </div>` : ''}

      <section>
        ${sectionHead('Indexed material')}
        ${docs.length
          ? raw(docs.map(docRow).join(''))
          : empty({
              icon: 'library',
              title: 'Nothing uploaded yet',
              body: 'Without your own material the tutor answers from its general knowledge and the web. Upload notes or a textbook chapter and answers start citing them.',
            })}
      </section>
    </div>`;
}

function docRow(doc) {
  return html`
    <article class="doc">
      <span class="doc-icon">${icon('library')}</span>
      <div class="grow">
        <strong class="truncate">${doc.filename}</strong>
        <p class="muted" style="font-size: var(--step--1)">
          ${doc.subject || 'General'} · ${doc.num_chunks} chunk${doc.num_chunks === 1 ? '' : 's'}
          ${doc.uploaded_at && doc.uploaded_at !== 'Unknown' ? ` · ${shortDate(doc.uploaded_at)}` : ''}
        </p>
      </div>
    </article>`;
}

async function refresh() {
  const data = await api.documents.list(state.student.id).catch(() => null);
  set({ documents: data?.documents || [] });
}

async function upload(host, file) {
  if (!file) return;
  if (file.size > MAX_MB * 1024 * 1024) {
    return toastErr(new Error(`${file.name} is larger than ${MAX_MB} MB.`));
  }

  uploading = true;
  draw(host);

  try {
    const result = await api.documents.upload({
      file,
      studentId: state.student.id,
      subject: $('#doc-subject', host)?.value?.trim() || null,
    });
    toast(`${result.filename} indexed as ${result.num_chunks} chunks.`, 'good');
    await refresh();
  } catch (error) {
    toastErr(error);
  } finally {
    uploading = false;
    draw(host);
  }
}

function draw(host) {
  render(host, html`<div class="pane scroll">${raw(screen())}</div>`);

  const drop = $('#drop', host);
  const input = $('#doc-file', host);
  if (!drop || uploading) return;

  drop.addEventListener('click', () => input.click());
  drop.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); input.click(); }
  });
  input.addEventListener('change', () => upload(host, input.files[0]));

  ['dragenter', 'dragover'].forEach((type) =>
    drop.addEventListener(type, (event) => { event.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach((type) =>
    drop.addEventListener(type, (event) => { event.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', (event) => upload(host, event.dataTransfer?.files?.[0]));
}

export async function mount(host) {
  draw(host);
  await refresh();
  draw(host);
}
