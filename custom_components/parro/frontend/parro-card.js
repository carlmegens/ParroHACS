/* Parro card 0.3.0 — content stays in this card's memory, never in entity states. */
const STRINGS = {
  nl: {
    announcements: 'Mededelingen', conversations: 'Gesprekken', source: 'Inhoud', conversation: 'Gesprek', message: 'Bericht',
    chooseConversation: 'Kies een gesprek', chooseConversationHint: 'Selecteer hierboven het gesprek dat je wilt lezen.',
    noConversations: 'Geen gesprekken', noConversationsHint: 'Er zijn geen gesprekken beschikbaar voor dit account.',
    conversationUnavailable: 'Gesprek niet beschikbaar', conversationUnavailableHint: 'Selecteer een ander gesprek of controleer de kaartinstellingen.',
    emptyMessages: 'Geen berichten', emptyMessagesHint: 'Er zijn nog geen berichten in dit gesprek.',
    selectOnCard: 'Kiezen in de kaart', openParro: 'Open Parro', backIntegration: 'Terug naar de Parro-integratie', backDevice: 'Terug naar het apparaat',
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
    announcements: 'Announcements', conversations: 'Conversations', source: 'Content', conversation: 'Conversation', message: 'Message',
    chooseConversation: 'Choose a conversation', chooseConversationHint: 'Select the conversation you want to read above.',
    noConversations: 'No conversations', noConversationsHint: 'No conversations are available for this account.',
    conversationUnavailable: 'Conversation unavailable', conversationUnavailableHint: 'Select another conversation or check the card settings.',
    emptyMessages: 'No messages', emptyMessagesHint: 'There are no messages in this conversation yet.',
    selectOnCard: 'Choose in the card', openParro: 'Open Parro', backIntegration: 'Back to the Parro integration', backDevice: 'Back to the device',
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
  const source = input.source ?? 'announcements';
  if (!['announcements', 'messages'].includes(source)) throw new Error('source must be announcements or messages');
  const chatroom = safeText(input.chatroom_id, 20);
  if (input.chatroom_id && (typeof input.chatroom_id !== 'string' || !/^[1-9][0-9]{0,19}$/.test(input.chatroom_id))) throw new Error('chatroom_id must be a positive numeric string');
  const limit = input.limit ?? 5;
  if (!Number.isInteger(limit) || limit < 1 || limit > 20) throw new Error('limit must be an integer from 1 to 20');
  return {
    type: 'custom:parro-card',
    config_entry_id: safeText(input.config_entry_id, 128),
    group_id: safeText(input.group_id, 128),
    source,
    chatroom_id: chatroom,
    title: safeText(input.title, 160),
    limit,
    show_images: input.show_images !== false,
  };
};
const CSS = `
  :host { display:block; font-family:var(--ha-font-family-body,Roboto, sans-serif); color:var(--primary-text-color,#212121); }
  :host([embedded]) ha-card { border:0; border-radius:0; background:transparent; }
  * { box-sizing:border-box; }
  .conversation-picker { padding:0 16px 16px; display:grid; gap:6px; }
  .conversation-picker label { color:var(--secondary-text-color,#606060); }
  .conversation-title { margin:0; font-size:16px; font-weight:500; overflow-wrap:anywhere; }
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
    this._conversations = [];
    this._roomId = '';
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
    this._roomId = config.chatroom_id;
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
    if (changedUser) { this._discard(); this._roomId = this._config.chatroom_id; this._render(); this._load(); }
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
    this._conversations = [];
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
      const response = await hass.callWS({ type: 'parro/accounts', ...(this._config.source === 'messages' ? { source: 'messages' } : {}) });
      if (epoch !== this._epoch) return;
      const accounts = Array.isArray(response?.accounts) ? response.accounts : [];
      if (!accounts.length) { this._error = 'noAccounts'; this._data = null; this._conversations = []; this._clearPhotos(); return; }
      const account = this._config.config_entry_id;
      if (!account) { this._error = 'choose'; this._data = null; return; }
      if (!accounts.some((item) => item.config_entry_id === account)) { this._error = 'unauthorized'; this._data = null; this._conversations = []; this._clearPhotos(); return; }
      let request;
      if (this._config.source === 'messages') {
        const rooms = await hass.callWS({ type: 'parro/conversations', config_entry_id: account, limit: 50 });
        if (epoch !== this._epoch) return;
        if (!Array.isArray(rooms?.items)) throw { code: 'unsupported_response' };
        this._conversations = rooms.items.slice(0, 50).filter((room) => room && typeof room.id === 'string' && /^[1-9][0-9]{0,19}$/.test(room.id));
        if (!this._conversations.length) { this._data = null; this._clearPhotos(); this._error = 'noConversations'; return; }
        if (!this._roomId) { this._data = null; this._error = 'chooseConversation'; return; }
        if (!this._conversations.some((room) => room.id === this._roomId)) { this._data = null; this._clearPhotos(); this._error = 'conversationUnavailable'; return; }
        request = { type: 'parro/messages', config_entry_id: account, chatroom_id: this._roomId, limit: this._config.limit };
      } else {
        request = { type: 'parro/feed', config_entry_id: account, limit: this._config.limit };
        if (this._config.group_id) request.group_id = this._config.group_id;
      }
      const data = await hass.callWS(request);
      if (epoch !== this._epoch) return;
      if (!Array.isArray(data?.items)) throw { code: 'unsupported_response' };
      this._clearPhotos();
      this._data = { ...data, items: data.items.slice(0, this._config.limit).filter((item) => item && typeof item === 'object') };
      this._expanded.clear();
    } catch (error) {
      if (epoch !== this._epoch) return;
      this._data = null;
      this._conversations = [];
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
  _selectRoom(id) {
    this._discard(); this._roomId = id; this._render(); this._load();
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
    const active = this.shadowRoot.activeElement;
    let pageActive = document.activeElement;
    while (pageActive?.shadowRoot?.activeElement) pageActive = pageActive.shadowRoot.activeElement;
    const focusId = ['conversation', 'refresh'].includes(active?.id) ? active.id
      : !active && (pageActive === document.body || pageActive === this) ? this._pendingFocus : null;
    this._pendingFocus = null;
    const t = words(this._hass);
    const style = el('style'); style.textContent = CSS;
    const card = el('ha-card');
    const header = el('div', 'header');
    const heading = el('div', 'heading');
    heading.append(el('h2', '', this._config.title || 'Parro'), el('p', 'subtitle', this._config.source === 'messages' ? t.conversations : t.messages));
    const refresh = button(t.refresh, () => this._load(true));
    refresh.id = 'refresh';
    refresh.append(icon('refresh'));
    refresh.disabled = this._loading || !this._hass;
    header.append(heading, refresh); card.append(header);
    card.setAttribute('aria-busy', String(Boolean(this._loading)));
    if (this._config.source === 'messages' && this._conversations.length) {
      const picker = el('div', 'conversation-picker');
      if (this._config.chatroom_id) {
        picker.append(el('p', 'conversation-title', safeText(this._conversations.find((room) => room.id === this._roomId)?.title, 500) || t.conversation));
      } else {
        const label = el('label', '', t.conversation); label.htmlFor = 'conversation';
        const select = el('select'); select.id = 'conversation';
        const empty = el('option', '', t.chooseConversation); empty.value = ''; select.append(empty);
        for (const room of this._conversations) { const option = el('option', '', safeText(room.title, 500) || t.conversation); option.value = room.id; select.append(option); }
        select.value = this._roomId; select.disabled = this._loading;
        select.addEventListener('change', () => this._selectRoom(select.value)); picker.append(label, select);
      }
      card.append(picker);
    }
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
      const key = this._error || (this._data ? (this._config.source === 'messages' ? 'emptyMessages' : 'empty') : 'choose');
      const state = el('div', 'state'); state.setAttribute('role', this._error && !['choose', 'noAccounts', 'chooseConversation', 'noConversations'].includes(key) ? 'alert' : 'status');
      state.append(icon(key === 'empty' ? 'message-text-outline' : key === 'unauthorized' ? 'lock-outline' : 'school-outline'), el('h3', '', t[key]), el('p', '', t[`${key}Hint`]));
      if (!['choose', 'noAccounts', 'empty', 'emptyMessages', 'chooseConversation', 'noConversations'].includes(key)) {
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
        const date = el('time', '', this._date(item.created_at || item.sort_date, this._config.source === 'messages'));
        if (date.textContent) date.dateTime = safeText(item.created_at || item.sort_date, 100);
        meta.append(date); article.append(meta);
        const key = `${index}:${safeText(item.id, 128)}`;
        const expanded = this._expanded.has(key);
        const title = safeText(item.title, 1000) || (this._config.source === 'messages' ? safeText(item.sender, 256) || t.message : t.untitled);
        const h3 = el('h3');
        const toggle = button(`${expanded ? t.close : t.read}: ${title}`, () => {
          if (expanded) this._expanded.delete(key); else this._expanded.add(key);
          this._render();
          this.shadowRoot.querySelector(`[data-index="${index}"]`)?.focus();
        }, 'toggle');
        toggle.dataset.index = index; toggle.setAttribute('aria-expanded', String(expanded)); toggle.setAttribute('aria-controls', `body-${index}`);
        toggle.append(el('span', '', title), icon(expanded ? 'chevron-up' : 'chevron-down')); h3.append(toggle); article.append(h3);
        if (item.sender && this._config.source !== 'messages') article.append(el('p', 'meta sender', safeText(item.sender, 256)));
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
    // Loading temporarily removes or disables these controls. Restore only if
    // focus has not moved elsewhere while the request was in flight.
    if (focusId && this.isConnected) {
      const target = this.shadowRoot.getElementById(focusId);
      if (target && !target.disabled) target.focus({ preventScroll: true });
      else if (this._loading || !this._started) this._pendingFocus = focusId;
    }
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
      const response = await this._hass.fetchWithAuth(`/api/parro/${encodeURIComponent(this._config.config_entry_id)}/${this._config.source === 'messages' ? 'chat_image' : 'image'}/${encodeURIComponent(id)}`, { signal: controller.signal });
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
    const sourceChanged = this._config.source !== next.source;
    const accountChanged = this._config.config_entry_id !== next.config_entry_id;
    this._config = next;
    this._render();
    if (sourceChanged) this._loadAccounts();
    else if (accountChanged) this._loadGroups();
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
      const result = await this._hass.callWS({ type: 'parro/accounts', ...(this._config.source === 'messages' ? { source: 'messages' } : {}) });
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
      const result = await this._hass.callWS(this._config.source === 'messages' ? { type: 'parro/conversations', config_entry_id: account, limit: 50 } : { type: 'parro/feed', config_entry_id: account, limit: 1 });
      if (epoch !== this._epoch) return;
      this._groups = this._config.source === 'messages' ? (Array.isArray(result?.items) ? result.items.slice(0, 50).map((room) => ({ id: room.id, name: room.title })) : []) : (Array.isArray(result?.groups) ? result.groups : []);
      this._error = null;
    } catch (error) {
      if (epoch !== this._epoch) return;
      this._error = errorCode(error);
      if (this._error === 'unauthorized') this._accounts = [];
    } finally { if (epoch === this._epoch) { this._groupsLoading = false; this._render(); } }
  }
  _change(key, value) {
    this._config = { ...this._config, [key]: value };
    if (key === 'config_entry_id' || key === 'source') { this._config.group_id = ''; this._config.chatroom_id = ''; this._groups = []; if (key === 'source') this._loadAccounts(); else this._loadGroups(); }
    const config = { ...this._config };
    for (const optional of ['title', 'group_id', 'chatroom_id', 'config_entry_id']) if (!config[optional]) delete config[optional];
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
    const source = select('source', [{ id: 'announcements', name: t.announcements }, { id: 'messages', name: t.conversations }], t.source); source.firstElementChild.remove(); field('source', t.source, source);
    const account = select('config_entry_id', this._accounts.map((item) => ({ id: safeText(item.config_entry_id, 128), name: safeText(item.title, 160) || 'Parro' })), t.choose);
    account.disabled = this._loading || !this._accounts.length; field('config_entry_id', t.account, account).append(el('p', 'hint', t.editorHint));
    const selection = this._config.source === 'messages' ? 'chatroom_id' : 'group_id';
    const group = select(selection, this._groups.map((item) => ({ id: safeText(item.id, 128), name: safeText(item.name, 160) })), this._groupsLoading ? t.loading : this._config.source === 'messages' ? t.selectOnCard : t.allGroups);
    group.disabled = this._groupsLoading || !this._config.config_entry_id; field(selection, this._config.source === 'messages' ? t.conversation : t.group, group);
    const title = el('input'); title.type = 'text'; title.value = this._config.title; title.placeholder = 'Parro'; title.maxLength = 160; title.addEventListener('change', () => this._change('title', title.value)); field('title', t.title, title);
    const limit = el('input'); limit.type = 'number'; limit.min = '1'; limit.max = '20'; limit.step = '1'; limit.value = this._config.limit; limit.addEventListener('change', () => { if (limit.reportValidity() && Number.isInteger(limit.valueAsNumber)) this._change('limit', limit.valueAsNumber); }); field('limit', t.limit, limit);
    const checkbox = el('label', 'checkbox'); const images = el('input'); images.type = 'checkbox'; images.checked = this._config.show_images; images.addEventListener('change', () => this._change('show_images', images.checked)); checkbox.append(images, el('span', '', t.images)); form.append(checkbox, el('p', 'hint', t.imageHint));
    if (this._error) { const error = el('p', 'notice', `${t[this._error]}. ${t[`${this._error}Hint`]}`); error.setAttribute('role', 'alert'); form.append(error); }
    this.shadowRoot.replaceChildren(style, form);
  }
}

// Home Assistant owns the surrounding more-info dialog and its focus management.
const deviceForAccount = (hass, account) => Object.values(hass?.devices || {}).find((device) => Array.isArray(device.config_entries) && device.config_entries.includes(account))?.id;
const internalLink = (label, path) => { const link = el('a', 'text-button', label); link.href = path; return link; };
const SURFACE_CSS = `${CSS}
  :host { min-width:0; }
  a.text-button { display:inline-flex; align-items:center; text-decoration:none; }
  .surface-link { padding:0 16px 12px; }
  .panel-shell { min-height:100%; background:var(--primary-background-color,#fafafa); }
  .panel-toolbar { display:flex; align-items:center; gap:12px; padding:8px 16px; min-height:64px; background:var(--app-header-background-color,var(--primary-background-color,#fafafa)); color:var(--app-header-text-color,var(--primary-text-color,#212121)); border-bottom:1px solid var(--divider-color,#e0e0e0); }
  .panel-toolbar h1 { margin:0; font-size:20px; font-weight:400; }
  .panel-content { max-width:800px; padding:20px 24px 32px; margin:0 auto; }
  .tabs { display:flex; border-bottom:1px solid var(--divider-color,#e0e0e0); margin-bottom:20px; }
  .tab { flex:1; min-height:48px; border:0; border-bottom:2px solid transparent; padding:12px; background:transparent; color:var(--secondary-text-color,#606060); font-weight:500; }
  .tab[aria-selected=true] { border-bottom-color:var(--primary-color,#03a9f4); color:var(--primary-text-color,#212121); }
  .tab:hover { background:var(--secondary-background-color,#f5f5f5); }
  .panel-account { display:grid; gap:6px; margin-bottom:20px; }
  @media(max-width:600px) { .panel-content { padding:12px 12px 24px; } }
`;
class MoreInfoParro extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: 'open' }); }
  set hass(value) { this._hass = value; this._sync(); }
  set stateObj(value) { this._stateObj = value; this._sync(); }
  connectedCallback() { this._sync(); }
  _sync() {
    if (!this.isConnected) return;
    if (!this._card) {
      const style = el('style'); style.textContent = SURFACE_CSS;
      this._card = el('parro-card'); this._card.setAttribute('embedded', '');
      this._links = el('div', 'surface-link'); this.shadowRoot.replaceChildren(style, this._card, this._links);
    }
    const attrs = this._stateObj?.attributes || {};
    const account = safeText(attrs.parro_config_entry_id, 128);
    const source = attrs.parro_source === 'messages' ? 'messages' : 'announcements';
    this._card.setConfig({ type: 'custom:parro-card', config_entry_id: account, source, limit: 20, show_images: true });
    if (this._stateObj) this._card.hass = this._hass;
    const signature = `${account}|${source}|${locale(this._hass)}`;
    if (this._linkSignature !== signature) {
      this._linkSignature = signature;
      this._links.replaceChildren(...(account ? [internalLink(words(this._hass).openParro, `/parro/${encodeURIComponent(account)}?source=${source}`)] : []));
    }
  }
}

// This panel is registered without a sidebar item. It is reached from the device.
class ParroPanel extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: 'open' }); this._source = 'announcements'; this._accounts = []; this._epoch = 0; this._account = ''; }
  set hass(value) {
    const changed = !this._hass || this._hass.user?.id !== value?.user?.id;
    this._hass = value;
    if (changed) { this._epoch++; this._accounts = []; this._account = ''; this._context = ''; }
    this._sync();
  }
  set route(value) {
    this._route = value;
    const query = new URLSearchParams(String(value?.path || '').split('?')[1] || window.location.search);
    if (['messages', 'announcements'].includes(query.get('source'))) this._source = query.get('source');
    this._sync();
  }
  set panel(value) { this._panel = value; this._sync(); }
  set narrow(value) { this.toggleAttribute('narrow', Boolean(value)); }
  connectedCallback() { this._sync(); }
  disconnectedCallback() { this._epoch++; this._accounts = []; this._context = ''; this._account = ''; if (this._card) this._renderControls(); }
  _routeAccount() {
    let value;
    try { value = decodeURIComponent(String(this._route?.path || '').split('?')[0].replace(/^\/parro(?=\/|$)/, '').replace(/^\//, '').replace(/\/$/, '')); } catch { return ''; }
    return /^[A-Za-z0-9_-]{1,128}$/.test(value) ? value : '';
  }
  _sync() {
    if (!this.isConnected) return;
    const routeAccount = this._routeAccount();
    const context = `${routeAccount}|${this._source}|${this._hass?.user?.id || ''}|${locale(this._hass)}`;
    if (!this._card) {
      const style = el('style'); style.textContent = SURFACE_CSS;
      const shell = el('div', 'panel-shell'); this._toolbar = el('div', 'panel-toolbar');
      const main = el('main', 'panel-content'); this._controls = el('div');
      this._card = el('parro-card'); this._card.id = 'parro-content'; this._card.setAttribute('role', 'tabpanel');
      main.append(this._controls, this._card); shell.append(this._toolbar, main); this.shadowRoot.replaceChildren(style, shell);
    }
    if (context !== this._context) {
      this._epoch++; this._context = context; this._accounts = []; this._account = routeAccount;
      this._renderControls();
      if (!routeAccount && this._hass) this._loadAccounts();
    }
    this._syncCard();
  }
  _syncCard() {
    this._card.setConfig({ type: 'custom:parro-card', config_entry_id: this._account, source: this._source, limit: 20, show_images: true });
    this._card.hass = this._hass;
  }
  async _loadAccounts() {
    const epoch = ++this._epoch; this._accountError = null;
    try {
      const result = await this._hass.callWS({ type: 'parro/accounts', ...(this._source === 'messages' ? { source: 'messages' } : {}) });
      if (epoch !== this._epoch) return;
      this._accounts = Array.isArray(result?.accounts) ? result.accounts : [];
    } catch (error) { if (epoch === this._epoch) this._accountError = errorCode(error); }
    if (epoch === this._epoch) this._renderControls();
  }
  _renderControls() {
    const t = words(this._hass);
    const device = deviceForAccount(this._hass, this._account);
    const back = internalLink(device ? t.backDevice : t.backIntegration, device ? `/config/devices/device/${encodeURIComponent(device)}` : '/config/integrations/integration/parro');
    back.className = 'icon-button'; back.setAttribute('aria-label', device ? t.backDevice : t.backIntegration); back.title = back.getAttribute('aria-label'); back.replaceChildren(icon('arrow-left'));
    this._toolbar.replaceChildren(back, el('h1', '', 'Parro'));
    const tabs = el('div', 'tabs'); tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', t.source);
    for (const [source, label] of [['announcements', t.announcements], ['messages', t.conversations]]) {
      const tab = button(label, () => { this._source = source; this._sync(); this.shadowRoot.querySelector(`#tab-${source}`)?.focus(); }, 'tab');
      tab.textContent = label; tab.id = `tab-${source}`; tab.setAttribute('role', 'tab'); tab.setAttribute('aria-selected', String(source === this._source)); tab.setAttribute('aria-controls', 'parro-content'); tab.tabIndex = source === this._source ? 0 : -1;
      tab.addEventListener('keydown', (event) => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) { event.preventDefault(); this._source = event.key === 'Home' ? 'announcements' : event.key === 'End' ? 'messages' : source === 'messages' ? 'announcements' : 'messages'; this._sync(); this.shadowRoot.querySelector(`#tab-${this._source}`)?.focus(); } }); tabs.append(tab);
    }
    this._card.setAttribute('aria-labelledby', `tab-${this._source}`);
    this._controls.replaceChildren(tabs);
    if (!this._routeAccount()) {
      const field = el('div', 'panel-account'); const label = el('label', '', t.account); label.htmlFor = 'panel-account';
      const select = el('select'); select.id = 'panel-account'; const placeholder = el('option', '', t.choose); placeholder.value = ''; select.append(placeholder);
      for (const account of this._accounts) { const option = el('option', '', safeText(account.title, 160) || 'Parro'); option.value = safeText(account.config_entry_id, 128); select.append(option); }
      select.value = this._account; select.disabled = !this._accounts.length;
      select.addEventListener('change', () => { this._account = select.value; this._syncCard(); this._renderControls(); }); field.append(label, select); this._controls.append(field);
      if (this._accountError) { const error = el('p', 'notice', t[this._accountError]); error.setAttribute('role', 'alert'); this._controls.append(error); }
    }
  }
}

if (!customElements.get('parro-card')) customElements.define('parro-card', ParroCard);
if (!customElements.get('parro-card-editor')) customElements.define('parro-card-editor', ParroCardEditor);
if (!customElements.get('more-info-parro')) customElements.define('more-info-parro', MoreInfoParro);
if (!customElements.get('parro-panel')) customElements.define('parro-panel', ParroPanel);
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === 'parro-card')) window.customCards.push({ type: 'parro-card', name: 'Parro', description: 'School announcements, conversations and photos from your Parro account.', preview: false });
