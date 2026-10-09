(() => {
  const config = __SHADOWOPS_CONFIG__;
  // Version one observes top-level documents, including new tabs, not iframes.
  if (window !== window.top || !config.allowed_origins.includes(location.origin)) return;
  const listeners = new AbortController();
  const dirty = new WeakSet();
  const pending = new Set();
  let active = true;
  let lastNavigation = null;

  const authHints = /password|passwd|passphrase|secret|token|auth|login|sign.?in|username|\b(?:pin|otp|cvv|cvc|ssn)\b/i;
  const privateHints = /email|phone|telephone|address|birth|credit|debit|card|iban|account|customer|payment|amount|balance|social.?security/i;
  const identifierHints = /transaction/i;
  const privateText = /[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b\d[\d ()+-]{8,}\d\b|\b(?:bearer\s+\S+|eyJ[\w-]+\.[\w-]+\.[\w-]+)|\b[A-Za-z0-9_-]{24,}\b|(?:password|secret|token|auth)\s*[:=]|[$€£]\s*\d/i;
  const cleanText = (text, limit = 1024) => {
    const value = String(text || '').replace(/\s+/g, ' ').trim();
    return !value || value.length > limit || privateText.test(value) ? null : value;
  };
  function cleanUrl() {
    const url = new URL(location.href);
    let path = url.pathname.split('/').map(part => {
      let decoded;
      try { decoded = decodeURIComponent(part); } catch { return '[redacted]'; }
      return /@|\d{6,}|[A-Za-z0-9_-]{24,}/.test(decoded) ? '[redacted]' : part;
    }).join('/');
    if (/password|secret|token|oauth|authorize|login|sign[-_]?in/i.test(path)) path = '/[redacted]';
    return url.origin + (path || '/'); // Queries and fragments are never sent.
  }
  function roleOf(element) {
    const explicit = cleanText(element.getAttribute('role'), 128);
    if (explicit) return explicit.split(' ')[0];
    const tag = element.localName;
    if (tag === 'button') return 'button';
    if (tag === 'a' && element.hasAttribute('href')) return 'link';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'nav') return 'navigation';
    if (tag === 'main') return 'main';
    if (tag === 'aside') return 'complementary';
    if (tag === 'fieldset') return 'group';
    if (tag === 'section' && labelOf(element)) return 'region';
    if (tag === 'form' && labelOf(element)) return 'form';
    if (tag === 'select') return element.multiple ? 'listbox' : 'combobox';
    if (tag === 'input') {
      if (['button', 'submit', 'reset'].includes(element.type)) return 'button';
      if (['checkbox', 'radio'].includes(element.type)) return element.type;
      if (element.type === 'number') return 'spinbutton';
      return 'textbox';
    }
    return null;
  }
  function semanticText(node, includeHidden = false) {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent;
    if (!(node instanceof Element)) return '';
    if (node.matches('input, textarea, select, script, style, template')) return '';
    const style = getComputedStyle(node);
    if (!includeHidden && (node.matches('[aria-hidden="true"], [hidden]') || style.display === 'none' || style.visibility === 'hidden')) return '';
    if (node.localName === 'img') return node.getAttribute('alt') || '';
    return [...node.childNodes].map(child => semanticText(child, includeHidden)).join(' ');
  }
  function labelOf(element) {
    const references = element.getAttribute('aria-labelledby');
    if (references) return cleanText(references.split(/\s+/).map(id => {
      const label = document.getElementById(id);
      return label ? semanticText(label, true) : '';
    }).join(' '));
    const aria = element.getAttribute('aria-label');
    if (aria) return cleanText(aria);
    if (element.labels?.length) return cleanText([...element.labels].map(label => semanticText(label)).join(' '));
    if (element.localName === 'fieldset') {
      const legend = element.querySelector(':scope > legend');
      if (legend) return cleanText(semanticText(legend));
    }
    if (element.matches('button, a, [role="button"], [role="link"]')) return cleanText(semanticText(element));
    // Never read input.value to derive a label, including submit/button inputs.
    return cleanText(element.getAttribute('title'));
  }
  function stableSelectors(element) {
    const selectors = [];
    for (const attribute of ['data-testid', 'id', 'name']) {
      const value = cleanText(element.getAttribute(attribute), 64);
      if (!value || !/^[A-Za-z_][\w-]*$/.test(value) || /^(react|radix|headless)/i.test(value)) continue;
      const css = attribute === 'id' ? '#' + CSS.escape(value) : `${element.localName}[${attribute}="${CSS.escape(value)}"]`;
      if (element.getRootNode().querySelectorAll(css).length === 1) selectors.push({attribute, value, css});
    }
    return selectors;
  }
  function contextOf(element) {
    for (let ancestor = element.parentElement; ancestor; ancestor = ancestor.parentElement) {
      if (!ancestor.matches('form, fieldset, section, article, nav, aside, main, [role="region"], [role="group"], [role="dialog"]')) continue;
      const label = labelOf(ancestor);
      const selector = stableSelectors(ancestor)[0]?.css || null;
      if (label || selector) return {tag: ancestor.localName, role: roleOf(ancestor), label, selector};
    }
    return null;
  }
  function forbidden(element) {
    if (element.matches('[hidden], [aria-hidden="true"], input[type="hidden"], input[type="password"], input[type="email"], input[type="tel"], input[type="file"]')) return true;
    if (!element.getClientRects().length) return true;
    const hints = [element.id, element.getAttribute('name'), element.getAttribute('autocomplete'), element.getAttribute('aria-label'), element.getAttribute('placeholder'), labelOf(element)].join(' ');
    if (authHints.test(hints) || /email|phone|telephone|social.?security/i.test(hints)) return true;
    const form = element.closest('form');
    return Boolean(form && (form.querySelector('input[type="password"]') || authHints.test([form.id, form.getAttribute('name'), form.getAttribute('action')].join(' '))));
  }
  function metadata(element) {
    const tag = element.localName;
    const role = roleOf(element);
    const label = labelOf(element);
    const placeholder = cleanText(element.getAttribute('placeholder'));
    const context = contextOf(element);
    const candidates = [];
    if (role && label) {
      const match_count = [...element.getRootNode().querySelectorAll('button, a, input, textarea, select, [role]')]
        .filter(node => node.getClientRects().length && roleOf(node) === role && labelOf(node) === label).length;
      candidates.push({strategy: 'role', value: role, name: label, match_count});
    }
    if (element.labels?.length && label) candidates.push({strategy: 'label', value: label});
    if (placeholder) candidates.push({strategy: 'placeholder', value: placeholder});
    let selector = null;
    for (const {attribute, value, css} of stableSelectors(element)) {
      if (attribute === 'data-testid') candidates.push({strategy: 'test_id', value});
      candidates.push({strategy: 'css', value: css, match_count: 1});
      if (!selector) selector = css;
    }
    if (!selector && context?.selector) {
      const css = `${context.selector} ${tag}`;
      if (element.getRootNode().querySelectorAll(css).length === 1) {
        selector = css;
        candidates.push({strategy: 'css', value: css, match_count: 1});
      }
    }
    return {tag, role, label, selector, placeholder, context, locator_candidates: candidates.slice(0, 8)};
  }
  function emit(action, target, extras = {}) {
    if (!active) return;
    const event = {action, target, timestamp: new Date().toISOString(), url: cleanUrl(), ...extras};
    // Invoke immediately, before page handlers can navigate or remove the target.
    const task = window.__shadowops_record(event).catch(() => {});
    pending.add(task);
    task.finally(() => pending.delete(task));
  }
  function commit(element, force = false) {
    if (!(element instanceof Element) || !element.matches('input, textarea, select') || forbidden(element)) return;
    if (!force && !dirty.has(element)) return;
    dirty.delete(element);
    const target = metadata(element);
    const extras = {};
    const isToggle = element.matches('input[type="checkbox"], input[type="radio"]');
    if (isToggle) extras.checked = element.checked;
    const allowed = config.value_allowlist.find(rule => {
      try { return rule.origin === location.origin && element.matches(rule.selector); } catch { return false; }
    });
    const hints = [element.id, element.getAttribute('name'), element.getAttribute('autocomplete'), target.label, target.placeholder].join(' ');
    const allowedType = element.matches('textarea, select') || ['text', 'search', 'number'].includes(element.type);
    if (!isToggle && allowed && allowedType && !privateHints.test(hints) && (!identifierHints.test(hints) || allowed.synthetic_identifier)) {
      const value = element.value;
      const validIdentifier = !allowed.synthetic_identifier || value === '' || /^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(value);
      // Empty values are meaningful; secret/PII patterns always override the allowlist.
      if (validIdentifier && value.length <= 4096 && !privateText.test(value) && !authHints.test(value)) {
        extras.value = value;
        extras._allowed_selector = allowed.selector;
      }
    }
    emit(element.localName === 'select' ? 'select_change' : 'input_change', target, extras);
  }
  const listen = (type, handler) => document.addEventListener(type, handler, {capture: true, signal: listeners.signal});
  listen('input', event => {
    if (event.isTrusted && event.target instanceof Element && !forbidden(event.target)) dirty.add(event.target);
  });
  listen('change', event => {
    if (event.isTrusted) commit(event.target, event.target.matches('select, input[type="checkbox"], input[type="radio"]'));
  });
  listen('focusout', event => { if (event.isTrusted) commit(event.target); });
  listen('submit', event => { if (event.isTrusted) commit(document.activeElement); });
  listen('click', event => {
    if (!event.isTrusted) return;
    const element = event.composedPath().find(node => node instanceof Element && node.matches('button, a[href], input[type="button"], input[type="submit"], input[type="reset"], [role="button"], [role="link"]'));
    if (element && !forbidden(element)) {
      commit(document.activeElement);
      emit('click', metadata(element));
    }
  });
  function navigation() {
    if (location.href === lastNavigation) return;
    lastNavigation = location.href;
    emit('navigation', {tag: 'document', role: null, label: null, selector: null});
  }
  for (const method of ['pushState', 'replaceState']) {
    const original = history[method];
    history[method] = function (...args) {
      const result = original.apply(this, args);
      navigation();
      return result;
    };
  }
  window.addEventListener('popstate', navigation, {signal: listeners.signal});
  window.addEventListener('hashchange', navigation, {signal: listeners.signal});
  window.addEventListener('pagehide', () => commit(document.activeElement), {signal: listeners.signal});
  document.addEventListener('DOMContentLoaded', navigation, {once: true, signal: listeners.signal});
  window.__shadowopsObserver = {
    stop: async () => {
      commit(document.activeElement);
      active = false;
      listeners.abort();
      await Promise.allSettled([...pending]);
    },
  };
})();
