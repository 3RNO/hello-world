// Capture the JSON a price site fetches, from inside your own browser.
//
// Why this rather than a scraper: it runs in your session, so bot
// protection, logins and geo-blocks are already satisfied, and it reads
// the site's own API responses rather than guessing at its markup. When
// the markup changes this keeps working.
//
// Use it on fut.gg, futbin, or easysbc.io:
//   1. Open the page you want prices from.
//   2. F12 -> Console -> paste this whole file -> Enter.
//   3. Reload the page, or click through to the data you want.
//   4. Run:  futdash.list()     to see what was captured
//   5. Run:  futdash.copy(2)    to copy capture #2 to your clipboard
//
// Nothing is sent anywhere. It only records responses in a variable.

(() => {
  if (window.futdash) {
    console.log('%cfutdash capture already running.', 'color:#4d9bff');
    return;
  }

  const captured = [];
  const MAX = 60;          // keep memory bounded
  const MIN_BYTES = 200;   // ignore trivial responses

  const looksInteresting = (url, body) => {
    if (!body || body.length < MIN_BYTES) return false;
    const t = body.trimStart();
    if (t[0] !== '{' && t[0] !== '[') return false;
    // Skip the noise every site emits.
    return !/analytics|telemetry|sentry|mixpanel|track|notification|\.(js|css|png|svg|woff)/i.test(url);
  };

  const record = (url, body) => {
    if (!looksInteresting(url, body)) return;
    captured.push({ n: captured.length, url, bytes: body.length, body });
    if (captured.length > MAX) captured.shift();
  };

  // --- fetch ---------------------------------------------------------
  const origFetch = window.fetch;
  window.fetch = function (...args) {
    return origFetch.apply(this, args).then((res) => {
      const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
      res.clone().text().then((b) => record(url, b)).catch(() => {});
      return res;
    });
  };

  // --- XMLHttpRequest ------------------------------------------------
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this.__futdashUrl = url;
    return origOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function (...args) {
    this.addEventListener('load', () => {
      try { record(this.__futdashUrl || '', this.responseText || ''); } catch (e) {}
    });
    return origSend.apply(this, args);
  };

  const summarise = (c) => {
    let hint = '';
    try {
      const j = JSON.parse(c.body);
      const keys = Array.isArray(j) ? `array[${j.length}]` : Object.keys(j).slice(0, 6).join(', ');
      hint = ` — ${keys}`;
    } catch (e) {}
    return `#${c.n}  ${(c.bytes / 1024).toFixed(1)} kB  ${c.url.slice(0, 90)}${hint}`;
  };

  window.futdash = {
    captured,
    list() {
      if (!captured.length) return console.log('Nothing captured yet — reload the page.');
      console.log('%cCaptured responses (biggest is usually the one you want):',
        'color:#4d9bff;font-weight:bold');
      [...captured].sort((a, b) => b.bytes - a.bytes).forEach((c) => console.log(summarise(c)));
      console.log('\\nCopy one with:  futdash.copy(<number>)');
    },
    get(n) { return captured.find((c) => c.n === n); },
    copy(n) {
      const c = n === undefined
        ? [...captured].sort((a, b) => b.bytes - a.bytes)[0]
        : captured.find((x) => x.n === n);
      if (!c) return console.log('No such capture.');
      copy(c.body);                        // DevTools' own clipboard helper
      console.log(`Copied #${c.n} (${(c.bytes / 1024).toFixed(1)} kB) from ${c.url}`);
    },
    biggest() { return [...captured].sort((a, b) => b.bytes - a.bytes)[0]; },
    clear() { captured.length = 0; console.log('Cleared.'); },
  };

  console.log('%cfutdash capture armed.', 'color:#35c26d;font-weight:bold');
  console.log('Now reload the page, then run:  futdash.list()');
})();
