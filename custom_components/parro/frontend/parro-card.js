/* Parro card 0.2.0 — content stays in this card's memory, never in entity states. */
const STRINGS = {
  nl: {
    messages: 'Schoolberichten', refresh: 'Vernieuwen', loading: 'Berichten ophalen…',
    empty: 'Geen mededelingen', emptyHint: 'Er zijn geen mededelingen voor deze selectie.',
    choose: 'Kies een Parro-account', chooseHint: 'Open de kaartinstellingen en selecteer je account.',
    noAccounts: 'Geen toegankelijk Parro-account', noAccountsHint: 'Voeg Parro toe bij Apparaten en diensten, of vraag de beheerder om toegang.',
    unauthorized: 'Geen toegang tot dit account', unauthorizedHint: 'Vraag de Home Assistant-beheerder om toegang tot dit Parro-account.',
    authentication_expired: 'Opnieuw aanmelden nodig', authentication_expiredHint: 'Meld je opnieuw aan bij Parro via Apparaten en diensten.',
    not_loaded: 'Parro is nog niet beschikbaar', not_loadedHint: 'Controleer de Parro-integratie bij Apparaten en diensten.',
    cannot_connect: 'Parro is niet bereikbaar', cannot_connectHint: 'Probeer het straks opnieuw.',
    unsupported_response: 'Berichten konden niet worden geladen', unsupported_responseHint: 'Probeer opnieuw of controleer of er een update voor Parro is.',
    updated: 'Bijgewerkt', stale: 'Tijdelijk eerder opgehaalde berichten', read: 'Bericht lezen', close: 'Bericht sluiten',
    photo: 'Foto', openPhoto: 'Foto vergroten', closePhoto: 'Vergrote foto sluiten', photoError: 'Foto niet beschikbaar',
    account: 'Account', group: 'Groep', allGroups: 'Alle groepen', title: 'Titel', limit: 'Aantal berichten',
    images: 'Foto’s tonen', editorHint: 'Alleen accounts waarvoor je toegang hebt, worden getoond.',
    imageHint: 'Maximaal 3 foto’s per bericht en 12 per kaart. Foto’s laden wanneer ze in beeld komen.',
    untitled: 'Mededeling', retry: 'Opnieuw proberen', noGroups: 'Groepen ophalen…',
  },
  en: {
    messages: 'School announcements', refresh: 'Refresh', loading: 'Loading announcements…',
    empty: 'No announcements', emptyHint: 'There are no announcements for this selection.',
    choose: 'Choose a Parro account', chooseHint: 'Open the card settings and select your account.',
    noAccounts: 'No accessible Parro account', noAccountsHint: 'Add Parro in Devices & services, or ask your administrator for access.',
    unauthorized: 'No access to this account', unauthorizedHint: 'Ask your Home Assistant administrator for access to this Parro account.',
    authentication_expired: 'Sign in again', authentication_expiredHint: 'Sign in to Parro again in Devices & services.',
    not_loaded: 'Parro is not available yet', not_loadedHint: 'Check the Parro integration in Devices & services.',
    cannot_connect: 'Cannot reach Parro', cannot_connectHint: 'Please try again later.',
    unsupported_response: 'Could not load announcements', unsupported_responseHint: 'Try again or check for a Parro update.',
    updated: 'Updated', stale: 'Showing previously fetched announcements temporarily', read: 'Read announcement', close: 'Close announcement',
    photo: 'Photo', openPhoto: 'Enlarge photo', closePhoto: 'Close enlarged photo', photoError: 'Photo unavailable',
    account: 'Account', group: 'Group', allGroups: 'All groups', title: 'Title', limit: 'Number of announcements',
    images: 'Show photos', editorHint: 'Only accounts you have permission to view are listed.',
    imageHint: 'Up to 3 photos per announcement and 12 per card. Photos load when they become visible.',
    untitled: 'Announcement', retry: 'Try again', noGroups: 'Loading groups…',
  },
};
const POLL_MS = 5 * 60 * 1000;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const safeText = (value, max = 20000) => typeof value === 'string' ? value.slice(0, max) : '';
const locale = (hass) => String(hass?.locale?.language || hass?.language || 'en');
const words = (hass) => STRINGS[locale(hass).toLowerCase().startsWith('nl') ? 'nl' : 'en'];
const errorCode = (error) => ['unauthorized', 'not_loaded', 'cannot_connect', 'authentication_expired', 'unsupported_response'].includes(error?.code) ? error.code : 'unsupported_response';
const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};
const icon = (name) => {
  const node = el('ha-icon');
  node.setAttribute('icon', `mdi:${name}`);
  node.setAttribute('aria-hidden', 'true');
  return node;
};
const button = (label, action, className = 'icon-button') => {
  const node = el('button', className);
  node.type = 'button';
  node.setAttribute('aria-label', label);
  node.title = label;
  node.addEventListener('click', action);
  return node;
};
const configValue = (input) => {
  if (!input || (input.type && input.type !== 'custom:parro-card')) throw new Error('Expected custom:parro-card');
  const limit = input.limit ?? 5;
  if (!Number.isInteger(limit) || limit < 1 || limit > 20) throw new Error('limit must be an integer from 1 to 20');
  return {
    type: 'custom:parro-card',
    config_entry_id: safeText(input.config_entry_id, 128),
    group_id: safeText(input.group_id, 128),
    title: safeText(input.title, 160),
    limit,
    show_images: input.show_images !== false,
  };
};
const CSS = `
  :host { display:block; font-family:var(--ha-font-family-body,Roboto, sans-serif); color:var(--primary-text-color,#212121); }
  * { box-sizing:border-box; }
  ha-card { display:block; background:var(--ha-card-background,var(--card-background-color,#fff)); border:var(--ha-card-border-width,1px) solid var(--ha-card-border-color,var(--divider-color,#e0e0e0)); border-radius:var(--ha-card-border-radius,12px); overflow:hidden; }
  button,input,select { font:inherit; color:inherit; caret-color:var(--primary-color,#03a9f4); }
  button { cursor:pointer; -webkit-tap-highlight-color:transparent; }
  button:disabled { cursor:default; opacity:.5; }
  button:focus-visible,input:focus-visible,select:focus-visible { outline:2px solid var(--primary-color,#03a9f4); outline-offset:2px; }
  ::selection { background:var(--primary-color,#03a9f4); color:var(--text-primary-color,#fff); }
  .header { display:flex; align-items:center; gap:12px; padding:16px 16px 12px; }
  .heading { min-width:0; flex:1; }
  h2 { margin:0; font-size:20px; line-height:1.4; font-weight:400; overflow-wrap:anywhere; }
  .subtitle,.meta,.footer,.hint { color:var(--secondary-text-color,#606060); font-size:13px; line-height:1.5; }
  .subtitle { margin:2px 0 0; }
  .icon-button { display:inline-flex; align-items:center; justify-content:center; width:44px; min-width:44px; height:44px; padding:10px; border:0; border-radius:50%; background:transparent; color:var(--secondary-text-color,#606060); }
  .icon-button:hover:not(:disabled),.toggle:hover { background:var(--secondary-background-color,#f5f5f5); }
  ha-icon { display:inline-block; width:24px; height:24px; --mdc-icon-size:24px; }
  .list { padding:0 16px; }
  article { padding:16px 0; border-top:1px solid var(--divider-color,#e0e0e0); }
  .meta { display:flex; flex-wrap:wrap; align-items:baseline; justify-content:space-between; gap:4px 12px; font-size:12px; }
  .group { font-weight:500; overflow-wrap:anywhere; }
  time { font-variant-numeric:tabular-nums; }
  h3 { margin:6px 0 0; font-size:16px; font-weight:500; line-height:1.5; }
  .toggle { display:flex; width:100%; align-items:start; gap:8px; text-align:start; padding:4px 0; border:0; border-radius:4px; background:transparent; min-height:44px; font-weight:500; }
  .toggle span { flex:1; min-width:0; overflow-wrap:anywhere; }
  .toggle ha-icon { flex:none; color:var(--secondary-text-color,#606060); }
  .sender { margin:0 0 8px; }
  .body { margin:0; font-size:14px; line-height:1.6; white-space:pre-wrap; overflow-wrap:anywhere; max-width:75ch; }
  .photos { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-top:12px; }
  .photo { display:flex; align-items:center; justify-content:center; width:100%; aspect-ratio:4/3; padding:0; border:0; border-radius:8px; background:var(--secondary-background-color,#f5f5f5); overflow:hidden; color:var(--secondary-text-color,#606060); }
  .photo img { width:100%; height:100%; object-fit:cover; }
  .photo[aria-expanded=true] { outline:2px solid var(--primary-color,#03a9f4); outline-offset:2px; }
  .photo.failed { padding:8px; font-size:12px; }
  .enlarged { margin-top:12px; }
  .enlarged img { display:block; width:100%; max-height:480px; object-fit:contain; border-radius:8px; }
  .close-photo { margin-top:4px; }
  .text-button { min-height:44px; border:0; border-radius:4px; padding:8px 12px; background:transparent; color:var(--primary-text-color,#212121); font-weight:500; text-decoration:underline; text-underline-offset:3px; }
  .text-button:hover { background:var(--secondary-background-color,#f5f5f5); }
  .footer { display:flex; align-items:center; gap:6px; padding:10px 16px 14px; font-size:12px; }
  .footer ha-icon { width:16px; height:16px; --mdc-icon-size:16px; }
  .notice { margin:0 16px 12px; padding:10px 12px; background:var(--secondary-background-color,#f5f5f5); border-radius:4px; font-size:13px; line-height:1.5; }
  .state { padding:24px 20px 28px; text-align:center; }
  .state > ha-icon { width:32px; height:32px; --mdc-icon-size:32px; color:var(--secondary-text-color,#606060); margin-bottom:8px; }
  .state h3 { margin:0 0 6px; }
  .state p { margin:0 auto 8px; max-width:40ch; font-size:14px; line-height:1.6; color:var(--secondary-text-color,#606060); }
  .skeleton { padding:0 16px 20px; }
  .skeleton-row { border-top:1px solid var(--divider-color,#e0e0e0); padding:20px 0 4px; }
  .skeleton-line { height:12px; background:var(--secondary-background-color,#f0f0f0); border-radius:3px; margin:0 0 12px; width:88%; }
  .skeleton-line:first-child { width:35%; height:10px; }
  .skeleton-line:nth-child(2) { width:68%; height:17px; }
  .editor { display:grid; gap:18px; padding:4px 0; }
  .field { display:grid; gap:6px; min-width:0; }
  label { font-size:14px; line-height:1.4; }
  input:not([type=checkbox]),select { width:100%; min-width:0; height:48px; border:1px solid var(--divider-color,#bdbdbd); background:var(--card-background-color,#fff); border-radius:4px; padding:0 12px; }
  input:disabled,select:disabled { opacity:.65; }
  input[type=checkbox] { width:20px; height:20px; accent-color:var(--primary-color,#03a9f4); }
  .checkbox { display:flex; align-items:center; gap:10px; min-height:44px; }
  .hint { margin:0; }
  .editor .notice { margin:0; }
  @media (prefers-reduced-motion:no-preference) { .icon-button,.toggle,.text-button { transition:background-color 160ms ease-out; } }
  @media (max-width:360px) { .header { padding:12px; } .list { padding:0 12px; } .meta { gap:2px 8px; } }
`;

class ParroCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = configValue({});
    this._epoch = 0;
    this._mediaEpoch = 0;
    this._expanded = new Set();
    this._urls = new Map();
    this._controllers = new Set();
    this._loadingPhotoIds = new Set();
    this._onVisibility = () => {
      if (document.visibilityState === 'hidden') { this._discard(); this._render(); }
      else this._load();
    };
  }
  static getStubConfig() { return { type: 'custom:parro-card', limit: 5, show_images: true }; }
  static getConfigElement() { return document.createElement('parro-card-editor'); }
  getCardSize() { return 2 + Math.min(this._data?.items?.length || 1, 5) * 3; }
  getGridOptions() { return { columns: 12, min_columns: 6 }; }
  setConfig(value) {
    const config = configValue(value);
    if (JSON.stringify(config) === JSON.stringify(this._config)) return;
    this._config = config;
    this._discard();
    this._render();
    this._load();
  }
  set hass(value) {
    const user = value?.user?.id;
    const changedUser = this._user !== user;
    const changedLanguage = this._language !== locale(value);
    this._hass = value;
    this._user = user;
    this._language = locale(value);
    if (changedUser) { this._discard(); this._render(); this._load(); }
    else if (!this._started) this._load();
    else if (changedLanguage) this._render();
  }
  connectedCallback() {
    this._connected = true;
    this._inView = !('IntersectionObserver' in window);
    document.addEventListener('visibilitychange', this._onVisibility);
    if ('IntersectionObserver' in window) {
      this._observer = new IntersectionObserver(([entry]) => {
        this._inView = entry.isIntersecting;
        if (this._inView) this._load();
        else clearTimeout(this._timer);
      });
      this._observer.observe(this);
    }
    this._render();
    this._load();
  }
  disconnectedCallback() {
    this._connected = false;
    document.removeEventListener('visibilitychange', this._onVisibility);
    this._observer?.disconnect();
    this._discard();
    this._render();
  }
  _eligible() { return this._connected && this._inView && document.visibilityState !== 'hidden'; }
  _clearPhotos() {
    this._mediaEpoch++;
    this._photoObserver?.disconnect();
    for (const controller of this._controllers) controller.abort();
    this._controllers.clear();
    this._loadingPhotoIds.clear();
    for (const url of this._urls.values()) URL.revokeObjectURL(url);
    this._urls.clear();
  }
  _discard() {
    this._epoch++;
    clearTimeout(this._timer);
    this._clearPhotos();
    this._data = null;
    this._error = null;
    this._loading = false;
    this._started = false;
    this._expanded.clear();
  }
  async _load(force = false) {
    if (!this._hass || !this._eligible() || this._loading) return;
    if (!force && this._started && Date.now() - this._loadedAt < POLL_MS) { this._schedule(); return; }
    const epoch = ++this._epoch;
    const hass = this._hass;
    this._loading = true;
    this._started = true;
    this._error = null;
    this._render();
    try {
      const response = await hass.callWS({ type: 'parro/accounts' });
      if (epoch !== this._epoch) return;
      const accounts = Array.isArray(response?.accounts) ? response.accounts : [];
      if (!accounts.length) { this._error = 'noAccounts'; this._data = null; this._clearPhotos(); return; }
      const account = this._config.config_entry_id;
      if (!account) { this._error = 'choose'; this._data = null; return; }
      if (!accounts.some((item) => item.config_entry_id === account)) { this._error = 'unauthorized'; this._data = null; this._clearPhotos(); return; }
      const request = { type: 'parro/feed', config_entry_id: account, limit: this._config.limit };
      if (this._config.group_id) request.group_id = this._config.group_id;
      const data = await hass.callWS(request);
      if (epoch !== this._epoch) return;
      if (!Array.isArray(data?.items)) throw { code: 'unsupported_response' };
      this._clearPhotos();
      this._data = { ...data, items: data.items.slice(0, this._config.limit).filter((item) => item && typeof item === 'object') };
      this._expanded.clear();
    } catch (error) {
      if (epoch !== this._epoch) return;
      this._data = null;
      this._error = errorCode(error);
      this._expanded.clear();
      this._clearPhotos();
    } finally {
      if (epoch === this._epoch) {
        this._loading = false;
        this._loadedAt = Date.now();
        this._render();
        this._schedule();
      }
    }
  }
  _schedule() {
    clearTimeout(this._timer);
    if (this._eligible() && this._config.config_entry_id) {
      this._timer = setTimeout(() => this._load(true), Math.max(1000, POLL_MS - (Date.now() - (this._loadedAt || 0))));
    }
  }
  _date(value, includeTime = false) {
    const date = new Date(value);
    if (!value || Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat(this._language || 'en', { dateStyle: 'medium', ...(includeTime ? { timeStyle: 'short' } : {}) }).format(date);
  }
  _render() {
    const t = words(this._hass);
    const style = el('style'); style.textContent = CSS;
    const card = el('ha-card');
    const header = el('div', 'header');
    const heading = el('div', 'heading');
    heading.append(el('h2', '', this._config.title || 'Parro'), el('p', 'subtitle', t.messages));
    const refresh = button(t.refresh, () => this._load(true));
    refresh.append(icon('refresh'));
    refresh.disabled = this._loading || !this._hass;
    header.append(heading, refresh); card.append(header);
    card.setAttribute('aria-busy', String(Boolean(this._loading)));
    if (this._loading && !this._data) {
      const skeleton = el('div', 'skeleton');
      skeleton.setAttribute('role', 'status'); skeleton.setAttribute('aria-label', t.loading);
      for (let i = 0; i < 2; i++) {
        const row = el('div', 'skeleton-row'); row.setAttribute('aria-hidden', 'true');
        for (let j = 0; j < 4; j++) row.append(el('div', 'skeleton-line'));
        skeleton.append(row);
      }
      card.append(skeleton);
    } else if (this._error || !this._data?.items.length) {
      const key = this._error || (this._data ? 'empty' : 'choose');
      const state = el('div', 'state'); state.setAttribute('role', this._error && !['choose', 'noAccounts'].includes(key) ? 'alert' : 'status');
      state.append(icon(key === 'empty' ? 'message-text-outline' : key === 'unauthorized' ? 'lock-outline' : 'school-outline'), el('h3', '', t[key]), el('p', '', t[`${key}Hint`]));
      if (!['choose', 'noAccounts', 'empty'].includes(key)) {
        const retry = button(t.retry, () => this._load(true), 'text-button'); retry.textContent = t.retry; state.append(retry);
      }
      card.append(state);
    } else {
      if (this._data.stale) { const notice = el('p', 'notice', t.stale); notice.setAttribute('role', 'status'); card.append(notice); }
      const list = el('div', 'list');
      let photosLeft = 12;
      this._data.items.forEach((item, index) => {
        const article = el('article');
        const meta = el('div', 'meta');
        meta.append(el('span', 'group', safeText(item.group_name, 160)));
        const date = el('time', '', this._date(item.created_at || item.sort_date));
        if (date.textContent) date.dateTime = safeText(item.created_at || item.sort_date, 100);
        meta.append(date); article.append(meta);
        const key = `${index}:${safeText(item.id, 128)}`;
        const expanded = this._expanded.has(key);
        const title = safeText(item.title, 1000) || t.untitled;
        const h3 = el('h3');
        const toggle = button(`${expanded ? t.close : t.read}: ${title}`, () => {
          if (expanded) this._expanded.delete(key); else this._expanded.add(key);
          this._render();
          this.shadowRoot.querySelector(`[data-index="${index}"]`)?.focus();
        }, 'toggle');
        toggle.dataset.index = index; toggle.setAttribute('aria-expanded', String(expanded)); toggle.setAttribute('aria-controls', `body-${index}`);
        toggle.append(el('span', '', title), icon(expanded ? 'chevron-up' : 'chevron-down')); h3.append(toggle); article.append(h3);
        if (item.sender) article.append(el('p', 'meta sender', safeText(item.sender, 256)));
        const contents = safeText(item.contents);
        const body = el('p', 'body', expanded || contents.length <= 180 ? contents : `${contents.slice(0, 180).trimEnd()}…`);
        body.id = `body-${index}`; article.append(body);
        const images = this._config.show_images && Array.isArray(item.images) ? item.images.slice(0, Math.min(3, photosLeft)) : [];
        if (images.length) {
          const grid = el('div', 'photos');
          for (const photo of images) {
            const id = safeText(photo?.id, 256);
            if (!id) continue;
            photosLeft--;
            const label = safeText(photo.name, 256) || `${t.photo} ${grid.children.length + 1}`;
            const photoButton = button(`${t.openPhoto}: ${label}`, () => this._enlarge(article, photoButton, id, label), 'photo');
            photoButton.dataset.imageId = id; photoButton.dataset.imageLabel = label; photoButton.setAttribute('aria-expanded', 'false');
            photoButton.append(icon('image-outline')); grid.append(photoButton);
            if (this._urls.has(id)) this._applyPhoto(photoButton, this._urls.get(id), label);
          }
          article.append(grid);
        }
        list.append(article);
      });
      card.append(list);
      const updated = this._date(this._data.updated_at, true);
      if (updated) { const footer = el('div', 'footer'); footer.append(icon('clock-outline'), el('span', '', `${t.updated} ${updated}`)); card.append(footer); }
    }
    this.shadowRoot.replaceChildren(style, card);
    this._observePhotos();
  }
  _observePhotos() {
    this._photoObserver?.disconnect();
    if (!this._eligible()) return;
    const nodes = [...this.shadowRoot.querySelectorAll('.photo')];
    if ('IntersectionObserver' in window) {
      this._photoObserver = new IntersectionObserver((entries) => {
        for (const entry of entries) if (entry.isIntersecting) {
          this._photoObserver.unobserve(entry.target);
          this._loadPhoto(entry.target);
        }
      }, { rootMargin: '100px' });
      nodes.forEach((node) => this._photoObserver.observe(node));
    } else nodes.forEach((node) => this._loadPhoto(node));
  }
  _applyPhoto(node, url, label) {
    const image = el('img'); image.src = url; image.alt = label; image.loading = 'lazy'; image.decoding = 'async';
    node.replaceChildren(image);
  }
  async _loadPhoto(node) {
    const id = node.dataset.imageId;
    if (this._urls.has(id) || this._loadingPhotoIds.has(id)) return;
    this._loadingPhotoIds.add(id);
    const epoch = this._epoch;
    const mediaEpoch = this._mediaEpoch;
    const controller = new AbortController(); this._controllers.add(controller);
    try {
      const response = await this._hass.fetchWithAuth(`/api/parro/${encodeURIComponent(this._config.config_entry_id)}/image/${encodeURIComponent(id)}`, { signal: controller.signal });
      if (epoch !== this._epoch || mediaEpoch !== this._mediaEpoch || !this._eligible()) return;
      if (response.status === 401 || response.status === 403) {
        this._discard(); this._error = 'unauthorized'; this._started = true; this._loadedAt = Date.now();
        this._render(); this._schedule(); return;
      }
      if (!response.ok) throw new Error('image_unavailable');
      const blob = await response.blob();
      if (epoch !== this._epoch || mediaEpoch !== this._mediaEpoch || !this._eligible()) return;
      if (!/^image\/(jpeg|png|webp|gif|avif)$/i.test(blob.type) || !blob.size || blob.size > MAX_IMAGE_BYTES) throw new Error('image_unavailable');
      const url = URL.createObjectURL(blob);
      const old = this._urls.get(id); if (old) URL.revokeObjectURL(old);
      this._urls.set(id, url);
      for (const current of this.shadowRoot.querySelectorAll('.photo')) if (current.dataset.imageId === id) this._applyPhoto(current, url, current.dataset.imageLabel);
    } catch (error) {
      if (epoch !== this._epoch || mediaEpoch !== this._mediaEpoch || error?.name === 'AbortError') return;
      node.replaceChildren(document.createTextNode(words(this._hass).photoError)); node.classList.add('failed');
    } finally {
      this._controllers.delete(controller);
      if (mediaEpoch === this._mediaEpoch) this._loadingPhotoIds.delete(id);
    }
  }
  _enlarge(article, node, id, label) {
    const existing = article.querySelector('.enlarged');
    article.querySelectorAll('.photo').forEach((photo) => photo.setAttribute('aria-expanded', 'false'));
    if (existing?.dataset.imageId === id) { existing.remove(); return; }
    existing?.remove();
    if (!this._urls.has(id)) { this._loadPhoto(node); return; }
    const section = el('div', 'enlarged'); section.dataset.imageId = id;
    const image = el('img'); image.src = this._urls.get(id); image.alt = label;
    const close = button(words(this._hass).closePhoto, () => { section.remove(); node.setAttribute('aria-expanded', 'false'); node.focus(); }, 'text-button close-photo');
    close.textContent = words(this._hass).closePhoto;
    section.append(image, close); article.append(section); node.setAttribute('aria-expanded', 'true');
  }
}

class ParroCardEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: 'open' }); this._config = configValue({}); this._accounts = []; this._groups = []; this._epoch = 0; }
  setConfig(value) {
    const next = configValue(value);
    const accountChanged = this._config.config_entry_id !== next.config_entry_id;
    this._config = next;
    this._render();
    if (accountChanged) this._loadGroups();
  }
  set hass(value) {
    const changed = !this._hass || this._hass.user?.id !== value?.user?.id;
    this._hass = value;
    if (changed) this._loadAccounts();
    else if (this._language !== locale(value)) this._render();
    this._language = locale(value);
  }
  connectedCallback() { this._render(); if (this._hass && !this._started) this._loadAccounts(); }
  disconnectedCallback() { this._epoch++; this._started = false; this._accounts = []; this._groups = []; this._render(); }
  async _loadAccounts() {
    if (!this._hass) return;
    const epoch = ++this._epoch; this._started = true; this._loading = true; this._error = null; this._accounts = []; this._groups = []; this._render();
    try {
      const result = await this._hass.callWS({ type: 'parro/accounts' });
      if (epoch !== this._epoch) return;
      this._accounts = Array.isArray(result?.accounts) ? result.accounts : [];
      this._loading = false;
      if (!this._accounts.length) this._error = 'noAccounts';
      if (this._accounts.some((account) => account.config_entry_id === this._config.config_entry_id)) await this._loadGroups();
    } catch (error) { if (epoch === this._epoch) { this._error = errorCode(error); this._loading = false; } }
    this._render();
  }
  async _loadGroups() {
    const account = this._config.config_entry_id;
    const epoch = ++this._epoch; this._groups = []; this._groupsLoading = false;
    if (!this._hass || !account || !this._accounts.some((item) => item.config_entry_id === account)) { this._render(); return; }
    this._groupsLoading = true; this._render();
    try {
      const result = await this._hass.callWS({ type: 'parro/feed', config_entry_id: account, limit: 1 });
      if (epoch !== this._epoch) return;
      this._groups = Array.isArray(result?.groups) ? result.groups : [];
      this._error = null;
    } catch (error) {
      if (epoch !== this._epoch) return;
      this._error = errorCode(error);
      if (this._error === 'unauthorized') this._accounts = [];
    } finally { if (epoch === this._epoch) { this._groupsLoading = false; this._render(); } }
  }
  _change(key, value) {
    this._config = { ...this._config, [key]: value };
    if (key === 'config_entry_id') { this._config.group_id = ''; this._groups = []; this._loadGroups(); }
    const config = { ...this._config };
    for (const optional of ['title', 'group_id', 'config_entry_id']) if (!config[optional]) delete config[optional];
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config }, bubbles: true, composed: true }));
  }
  _render() {
    const t = words(this._hass); const style = el('style'); style.textContent = CSS; const form = el('div', 'editor');
    const field = (name, label, node) => { const wrap = el('div', 'field'); node.id = name; const caption = el('label', '', label); caption.htmlFor = name; wrap.append(caption, node); form.append(wrap); return wrap; };
    const select = (name, entries, placeholder) => {
      const node = el('select'); const option = el('option', '', placeholder); option.value = ''; node.append(option);
      for (const entry of entries) { const option = el('option', '', entry.name); option.value = entry.id; node.append(option); }
      node.value = this._config[name]; node.addEventListener('change', () => this._change(name, node.value)); return node;
    };
    const account = select('config_entry_id', this._accounts.map((item) => ({ id: safeText(item.config_entry_id, 128), name: safeText(item.title, 160) || 'Parro' })), t.choose);
    account.disabled = this._loading || !this._accounts.length; field('config_entry_id', t.account, account).append(el('p', 'hint', t.editorHint));
    const group = select('group_id', this._groups.map((item) => ({ id: safeText(item.id, 128), name: safeText(item.name, 160) })), this._groupsLoading ? t.noGroups : t.allGroups);
    group.disabled = this._groupsLoading || !this._config.config_entry_id; field('group_id', t.group, group);
    const title = el('input'); title.type = 'text'; title.value = this._config.title; title.placeholder = 'Parro'; title.maxLength = 160; title.addEventListener('change', () => this._change('title', title.value)); field('title', t.title, title);
    const limit = el('input'); limit.type = 'number'; limit.min = '1'; limit.max = '20'; limit.step = '1'; limit.value = this._config.limit; limit.addEventListener('change', () => { if (limit.reportValidity() && Number.isInteger(limit.valueAsNumber)) this._change('limit', limit.valueAsNumber); }); field('limit', t.limit, limit);
    const checkbox = el('label', 'checkbox'); const images = el('input'); images.type = 'checkbox'; images.checked = this._config.show_images; images.addEventListener('change', () => this._change('show_images', images.checked)); checkbox.append(images, el('span', '', t.images)); form.append(checkbox, el('p', 'hint', t.imageHint));
    if (this._error) { const error = el('p', 'notice', `${t[this._error]}. ${t[`${this._error}Hint`]}`); error.setAttribute('role', 'alert'); form.append(error); }
    this.shadowRoot.replaceChildren(style, form);
  }
}

if (!customElements.get('parro-card')) customElements.define('parro-card', ParroCard);
if (!customElements.get('parro-card-editor')) customElements.define('parro-card-editor', ParroCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === 'parro-card')) window.customCards.push({ type: 'parro-card', name: 'Parro', description: 'School announcements and photos from your Parro account.', preview: false });
