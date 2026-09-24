// Pull a "cheapest player by rating" table out of a price site.
//
// Works on fut.gg/cheapest-by-rating and FUTBIN's cheapest-players page,
// and should survive most layout changes because it reads numbers rather
// than class names.
//
//   1. Open the cheapest-by-rating page. SET THE PLATFORM TO PC.
//   2. F12 -> Console -> paste this whole file -> Enter.
//   3. It prints the JSON and copies it to your clipboard.
//   4. Paste it into FUT Dash's Fodder tab.
//
// Check the printed table against the page before trusting it. If a row
// looks wrong, say so rather than importing it.

(() => {
  const RATING_MIN = 40, RATING_MAX = 99;
  const PRICE_MIN = 150;

  const num = (s) => {
    if (!s) return null;
    // "12,500", "12.5K", "1.2M", "12 500"
    const t = String(s).trim().replace(/[\s,]/g, '');
    let m = t.match(/^(\d+(?:\.\d+)?)([KkMm])?$/);
    if (!m) return null;
    let v = parseFloat(m[1]);
    if (m[2]) v *= /[Kk]/.test(m[2]) ? 1e3 : 1e6;
    return Math.round(v);
  };

  // Candidate rows: anything that renders as a row or card.
  const rows = [...document.querySelectorAll('tr, li, [class*="row"], [class*="card"], [class*="item"]')];
  const found = new Map();

  for (const row of rows) {
    const cells = [...row.querySelectorAll('td, span, div, p')]
      .map((el) => (el.childElementCount === 0 ? el.textContent.trim() : ''))
      .filter(Boolean);
    if (cells.length < 2) continue;

    const nums = cells.map(num).filter((n) => n !== null);
    const rating = nums.find((n) => n >= RATING_MIN && n <= RATING_MAX && Number.isInteger(n));
    // The price is the largest number on the row that is not the rating.
    const prices = nums.filter((n) => n >= PRICE_MIN && n !== rating);
    if (rating === undefined || !prices.length) continue;

    const price = Math.max(...prices);
    // Keep the cheapest sighting per rating -- the page may list several.
    if (!found.has(rating) || price < found.get(rating)) found.set(rating, price);
  }

  if (!found.size) {
    console.log('%cFound nothing.', 'color:#ff6b5b;font-weight:bold');
    console.log('Either the page has not finished loading, or its layout does not '
      + 'match. Try tools/capture-api.js instead — it reads the site\'s API directly.');
    return;
  }

  const out = {};
  [...found.keys()].sort((a, b) => a - b).forEach((r) => { out[r] = found.get(r); });

  console.log('%cCheck these against the page before importing:',
    'color:#e3b341;font-weight:bold');
  console.table(Object.entries(out).map(([rating, price]) => ({ rating: +rating, price })));

  const json = JSON.stringify(out);
  try { copy(json); console.log('%cCopied to clipboard.', 'color:#35c26d'); }
  catch (e) { console.log('Copy this:\n' + json); }
  console.log(`${found.size} ratings. Paste into FUT Dash -> Fodder tab.`);
  return out;
})();
