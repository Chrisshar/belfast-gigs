// The header search box. On wide screens it's always there; on phones (see .site-header.searching
// in global.css) it folds behind a magnifier icon and opens over the header bar. On the homepage,
// src/scripts/filters.ts filters as you type and keeps it in step with the filter bar's box;
// elsewhere, submitting goes to the homepage with ?q=.

export function initSearch(): void {
  // The ✕ inside each search box (shown by CSS only while it has text). Firing input lets
  // filters.ts update the listing and the other box.
  for (const button of document.querySelectorAll<HTMLButtonElement>('.search-clear')) {
    button.addEventListener('click', () => {
      const box = button.parentElement?.querySelector<HTMLInputElement>('input[type=search]');
      if (!box) return;
      box.value = '';
      box.dispatchEvent(new Event('input', { bubbles: true }));
      box.focus();
    });
  }

  const header = document.querySelector<HTMLElement>('.site-header');
  const form = header?.querySelector<HTMLFormElement>('.site-search');
  const input = form?.querySelector<HTMLInputElement>('input[name=q]');
  const open = header?.querySelector<HTMLButtonElement>('.search-open');
  const close = header?.querySelector<HTMLButtonElement>('.search-close');
  if (!header || !form || !input || !open || !close) return;

  const show = (focus: boolean): void => {
    header.classList.add('searching');
    open.setAttribute('aria-expanded', 'true');
    if (focus) input.focus();
  };

  // Closing clears the search, so a phone never hides an active filter behind the icon.
  const hide = (): void => {
    header.classList.remove('searching');
    open.setAttribute('aria-expanded', 'false');
    if (input.value) {
      input.value = '';
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    open.focus();
  };

  open.addEventListener('click', () => show(true));
  close.addEventListener('click', hide);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && header.classList.contains('searching')) hide();
  });
  // An empty search goes nowhere.
  form.addEventListener('submit', (event) => {
    if (!input.value.trim()) event.preventDefault();
  });

  // Arriving with a search applied: start open, so it's clear why the list is filtered. No focus,
  // which would pop up the keyboard.
  if (location.pathname === '/' && new URLSearchParams(location.search).get('q')) show(false);
}
