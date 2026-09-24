'use strict';

const $ = (s) => document.querySelector(s);
const state = { platform: 'pc', players: [] };

const coins = (n) => (n === null || n === undefined) ? '—' : Math.round(n).toLocaleString();
const signed = (n) => (n === null || n === undefined) ? '—'
  : (n > 0 ? '+' : '') + Math.round(n).toLocaleString();
const pct = (n) => (n === null || n === undefined) ? '—' : (n > 0 ? '+' : '') + n.toFixed(1) + '%';
const cls = (n) => n > 0 ? 'good' : n < 0 ? 'bad' : '';

async function get(path, params = {}) {
  const q = new URLSearchParams({ platform: state.platform, ...params });
  const r = await fetch(`${path}?${q}`);
  return r.json();
}
async function post(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platform: state.platform, ...body }),
  });
  return r.json();
}

let toastTimer;
function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 2600);
}

/** Minimal table renderer. cols: [{h, k, fmt, cls, num}] */
function table(rows, cols, emptyMsg) {
  if (!rows || !rows.length) return `<p class="empty">${emptyMsg}</p>`;
  const head = cols.map((c) => `<th class="${c.num ? 'num' : ''}">${c.h}</th>`).join('');
  const cell = (r, c) => {
    const v = c.fmt ? c.fmt(r[c.k], r) : (r[c.k] ?? '—');
    const extra = c.cls ? c.cls(r[c.k], r) : '';
    return `<td class="${c.num ? 'num' : ''} ${extra}">${v}</td>`;
  };
  const body = rows.map((r) => `<tr>${cols.map((c) => cell(r, c)).join('')}</tr>`).join('');
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

const nameCell = (_, r) => `${r.name}${r.rating ? ` <span class="sub">${r.rating}</span>` : ''}`;

// ---- tabs ----------------------------------------------------------------
async function loadStats() {
  const s = await get('/api/summary');
  const j = s.journal;
  $('#context').textContent = `FC ${s.game_year} · ${s.platform.toUpperCase()} · ${s.tracked_players} cards tracked`;
  $('#stats').innerHTML = [
    ['Realised profit', signed(j.profit), cls(j.profit)],
    ['Return on spend', pct(j.roi * 100), cls(j.roi)],
    ['Win rate', j.closed_trades ? (j.win_rate * 100).toFixed(0) + '%' : '—', ''],
    ['Closed trades', j.closed_trades, ''],
    ['Coins tied up', coins(j.capital_tied_up), ''],
  ].map(([k, v, c]) => `<div class="tile"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join('');
}

async function loadMarket() {
  const [dips, movers] = await Promise.all([get('/api/dips'), get('/api/movers')]);
  $('#dips').innerHTML = table(dips, [
    { h: 'Card', k: 'name', fmt: nameCell },
    { h: 'Now', k: 'price', fmt: coins, num: true },
    { h: 'Median', k: 'median', fmt: coins, num: true },
    { h: 'Discount', k: 'discount_pct', num: true, fmt: (v) => '-' + v.toFixed(1) + '%', cls: () => 'good' },
    { h: 'At median', k: 'profit_at_median', fmt: signed, num: true, cls: (v) => cls(v) },
    { h: '', k: 'new_low', fmt: (v, r) => (v ? '<span class="warn">new low</span>' : '') + (r.samples < 5 ? ' <span class="sub">thin</span>' : '') },
  ], 'No cards below their median yet — record some prices first.');

  const moverCols = [
    { h: 'Card', k: 'name', fmt: nameCell },
    { h: 'Price', k: 'price', fmt: coins, num: true },
    { h: 'Change', k: 'change_pct', fmt: pct, num: true, cls: (v) => cls(v) },
  ];
  $('#movers-up').innerHTML = table(movers.up, moverCols, 'Not enough history.');
  $('#movers-down').innerHTML = table(movers.down, moverCols, 'Not enough history.');
}

function snipeCard(r) {
  if (!r) return '<p class="empty">No price history for that card yet.</p>';
  const conf = r.confidence === 'high' ? '' : r.confidence === 'insufficient'
    ? '<span class="bad">too little history to trust this</span>'
    : `<span class="warn">${r.confidence} confidence, ${r.samples} snapshots</span>`;
  return `<div class="callout">
    <div class="grid3">
      <div><div class="k sub">Max buy-now</div><div class="big">${coins(r.max_buy_now)}</div></div>
      <div><div class="k sub">Max bid</div><div class="big">${coins(r.max_bid)}</div></div>
      <div><div class="k sub">Relist at</div><div class="big">${coins(r.relist_at)}</div></div>
      <div><div class="k sub">Profit / flip</div><div class="big ${cls(r.profit_per_flip)}">${signed(r.profit_per_flip)}</div></div>
    </div>
    <p class="hint" style="margin-top:10px">
      ${r.name} · market now ${coins(r.market_now)} · break-even ${coins(r.break_even)} ${conf}
      ${r.already_cheap ? '<br><strong class="good">Already at or below your max — worth a look now.</strong>' : ''}
    </p>
  </div>`;
}

async function loadSnipe() {
  const w = await get('/api/snipe');
  $('#watchlist').innerHTML = table(w, [
    { h: 'Card', k: 'name', fmt: nameCell },
    { h: 'Max buy', k: 'max_buy_now', fmt: coins, num: true },
    { h: 'Max bid', k: 'max_bid', fmt: coins, num: true },
    { h: 'Relist', k: 'relist_at', fmt: coins, num: true },
    { h: 'Per flip', k: 'profit_per_flip', fmt: signed, num: true, cls: (v) => cls(v) },
    { h: '', k: 'already_cheap', fmt: (v) => (v ? '<span class="good">cheap now</span>' : '') },
  ], 'Watchlist is empty. Calculate a filter above, then add the card.');
}

async function loadFodder() {
  const f = await get('/api/fodder');
  const best = new Set((f.best_value || []).slice(0, 3).map((r) => r.rating));
  $('#fodder-table').innerHTML = table(f.table, [
    { h: 'Rating', k: 'rating' },
    { h: 'Cheapest', k: 'price', fmt: coins, num: true },
    { h: 'Step cost', k: 'step_cost', fmt: (v) => (v === null ? '—' : signed(v)), num: true },
    { h: 'Step ratio', k: 'step_ratio', fmt: (v) => (v === null ? '—' : v.toFixed(2) + '×'), num: true },
    { h: '', k: 'rating', fmt: (v) => (best.has(v) ? '<span class="good">best value</span>' : '') },
  ], 'No rating prices recorded. Add the cheapest price per rating above.');

  $('#fodder-movement').innerHTML = table(f.movement, [
    { h: 'Rating', k: 'rating' },
    { h: 'Was', k: 'first', fmt: (x) => (x == null ? '—' : coins(x)), num: true },
    { h: 'Now', k: 'latest', fmt: coins, num: true },
    { h: 'Change', k: 'change_pct', num: true,
      // A rising fodder price is bad news for a buyer, so the colour is inverted.
      fmt: (x) => (x == null ? '<span class="sub">first reading</span>' : pct(x)),
      cls: (x) => (x == null ? '' : cls(-x)) },
    { h: 'Readings', k: 'samples', num: true },
  ], 'Nothing recorded yet.');
}

async function loadClub() {
  const c = await get('/api/club');
  const v = c.value;
  const s = c.stats;
  if (s) {
    $('#stats').innerHTML = [
      ['Coins', coins(s.coins), ''],
      ['Club value', coins(s.club_value), ''],
      ['Potential coins', coins(s.potential_coins), ''],
      ['On transfer list', coins(s.transfer_list), ''],
      ['SBC fodder score', coins(s.sbc_fodder), ''],
      ['Players', s.players_count, ''],
    ].map(([k, val, cl]) => `<div class="tile"><div class="k">${k}</div><div class="v ${cl}">${val}</div></div>`).join('');
  }

  const best = new Set((c.best_buys || []).slice(0, 3).map((r) => r.rating));
  $('#club-ladder').innerHTML = table(c.ladder, [
    { h: 'Rating', k: 'rating' },
    { h: 'Held', k: 'count', num: true },
    { h: 'Score / card', k: 'score_per_card', fmt: (x) => x.toFixed(0), num: true },
    { h: 'Price', k: 'price', fmt: (x) => (x == null ? '—' : coins(x)), num: true },
    { h: 'Score / coin', k: 'score_per_coin', num: true,
      fmt: (x) => (x == null ? '<span class="sub">no price</span>' : x.toFixed(4)),
      cls: (x, r) => (best.has(r.rating) ? 'good' : '') },
    { h: '', k: 'rating', fmt: (x) => (best.has(x) ? '<span class="good">best value</span>' : '') },
  ], 'Import your club stats above to see the fodder ladder.');

  const lines = [];
  if (s) {
    lines.push(`${s.club_name} · rank ${coins(s.rank)} · ${s.players_count} players` +
      (s.scanned_at ? ` · scanned ${s.scanned_at.slice(0, 16).replace('T', ' ')}` : ''));
  }
  if (v.cards) {
    lines.push(`${v.cards} cards imported, ${v.tradeable_cards} tradeable, worth ` +
      `<strong>${coins(v.after_tax)}</strong> after tax` +
      (v.unpriced_cards ? ` · <span class="warn">${v.unpriced_cards} without a price</span>` : ''));
  }
  $('#club-status').innerHTML = lines.length
    ? `<p class="hint" style="padding:0 16px 14px">${lines.join('<br>')}</p>`
    : '<p class="empty">Nothing imported yet.</p>';

  $('#club-inventory').innerHTML = table(c.gaps.length ? c.gaps : c.inventory, [
    { h: 'Rating', k: 'rating' },
    { h: 'Held', k: 'have', fmt: (v, r) => (v ?? r.total ?? 0) },
    { h: 'Cheapest', k: 'price', fmt: coins, num: true },
    { h: 'Step ratio', k: 'step_ratio', fmt: (v) => (v == null ? '—' : v.toFixed(2) + '×'), num: true },
  ], 'Import your club to see what you are holding.');
}

async function loadHoldings() {
  const [h, promos] = await Promise.all([get('/api/holdings'), get('/api/promos')]);
  $('#holdings').innerHTML = table(h, [
    { h: 'Card', k: 'name', fmt: nameCell },
    { h: 'Paid', k: 'buy_price', fmt: coins, num: true },
    { h: 'Break-even', k: 'break_even', fmt: coins, num: true },
    { h: 'Market', k: 'market', fmt: coins, num: true },
    { h: 'Unrealised', k: 'unrealised', fmt: signed, num: true, cls: (v) => cls(v) },
    { h: '', k: 'id', fmt: (v, r) => `<button class="ghost sell" data-id="${v}" data-name="${r.name}">Sell</button>` },
  ], 'Nothing held. Buys you log show up here until you sell them.');

  $('#promos').innerHTML = table(promos, [
    { h: 'Promo', k: 'name' },
    { h: 'Starts', k: 'starts_at', fmt: (v) => (v ? v.slice(0, 10) : '—') },
    { h: 'Ends', k: 'ends_at', fmt: (v) => (v ? v.slice(0, 10) : '—') },
  ], 'No promos recorded.');

  document.querySelectorAll('.sell').forEach((b) => {
    b.onclick = async () => {
      const price = prompt(`Sold ${b.dataset.name} for how many coins?`);
      if (!price) return;
      const res = await post('/api/trades/close', { trade_id: +b.dataset.id, sell_price: +price });
      toast(res.error ? res.error : `Logged: ${signed(res.profit)} coins after tax`);
      refresh();
    };
  });
}

async function loadJournal() {
  const [perf, trades] = await Promise.all([get('/api/performance'), get('/api/trades')]);
  $('#by-method').innerHTML = table(perf.by_method, [
    { h: 'Method', k: 'method' },
    { h: 'Trades', k: 'trades', num: true },
    { h: 'Profit', k: 'profit', fmt: signed, num: true, cls: (v) => cls(v) },
    { h: 'ROI', k: 'roi', fmt: (v) => pct(v * 100), num: true, cls: (v) => cls(v) },
    { h: 'Win rate', k: 'win_rate', fmt: (v) => (v * 100).toFixed(0) + '%', num: true },
  ], 'No closed trades yet.');

  $('#trades').innerHTML = table(trades, [
    { h: 'Card', k: 'name', fmt: nameCell },
    { h: 'Method', k: 'method' },
    { h: 'Bought', k: 'buy_price', fmt: coins, num: true },
    { h: 'Sold', k: 'sell_price', fmt: (v) => (v === null ? '<span class="sub">open</span>' : coins(v)), num: true },
    { h: 'Profit', k: 'profit', fmt: (v) => (v === null ? '—' : signed(v)), num: true, cls: (v) => cls(v) },
  ], 'No trades logged yet.');
}

let playerView = { id: null, days: 30, table: false };

async function loadPlayer() {
  if (!playerView.id) {
    $('#player-summary').innerHTML = '<p class="empty">Search for a card above.</p>';
    $('#player-chart').textContent = '';
    return;
  }
  const d = await get('/api/player', { player_id: playerView.id, days: playerView.days });
  if (d.error) return toast(d.error);
  const st = d.stats, f = d.filter;
  $('#player-chart-title').textContent =
    `${d.player.name}${d.player.rating ? ` (${d.player.rating})` : ''} — price history`;

  $('#player-summary').innerHTML = st ? `<div class="tiles" style="padding:0 16px 16px">${[
    ['Now', coins(st.latest), ''],
    ['Median', coins(st.median), ''],
    ['Low', coins(st.low), ''],
    ['High', coins(st.high), ''],
    ['vs median', pct(st.vs_median_pct), cls(-st.vs_median_pct)],
    ['Snipe under', f ? coins(f.max_buy_now) : '—', ''],
  ].map(([k, v, c]) => `<div class="tile"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join('')}</div>`
    : '<p class="empty">No prices recorded for this card yet.</p>';

  const pts = (d.history || []).map((h) => ({ ts: h.ts, price: h.price, source: h.source }));
  if (playerView.table) {
    $('#player-table').innerHTML = window.futdashChart.priceTable(pts);
    $('#player-table').classList.remove('hidden');
    $('#player-chart').classList.add('hidden');
  } else {
    $('#player-table').classList.add('hidden');
    $('#player-chart').classList.remove('hidden');
    window.futdashChart.priceChart($('#player-chart'), pts,
      { label: `Price history for ${d.player.name}` });
  }
}

async function loadPlayers() {
  state.players = await get('/api/players');
  $('#player-list').innerHTML = state.players
    .map((p) => `<option value="${p.name}">`).join('');
}

async function refresh() {
  await Promise.all([loadStats(), loadPlayers()]);
  const tab = document.querySelector('nav button.active').dataset.tab;
  await ({ market: loadMarket, player: loadPlayer, snipe: loadSnipe, fodder: loadFodder,
    club: loadClub, holdings: loadHoldings, journal: loadJournal }[tab])();
}

// ---- wiring --------------------------------------------------------------
document.querySelectorAll('#tabs button').forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll('#tabs button').forEach((x) => x.classList.remove('active'));
    b.classList.add('active');
    document.querySelectorAll('.tab').forEach((s) => s.classList.add('hidden'));
    $(`#tab-${b.dataset.tab}`).classList.remove('hidden');
    refresh();
  };
});

$('#platform').onchange = (e) => { state.platform = e.target.value; refresh(); };
$('#refresh').onclick = refresh;

$('#snipe-form').onsubmit = async (e) => {
  e.preventDefault();
  const name = $('#snipe-player').value.trim();
  const p = state.players.find((x) => x.name.toLowerCase() === name.toLowerCase());
  if (!p) return toast('No prices recorded for that card yet.');
  const r = await get('/api/snipe', { player_id: p.id, margin: +$('#snipe-margin').value / 100 });
  $('#snipe-result').innerHTML = snipeCard(r);
};

$('#fodder-form').onsubmit = async (e) => {
  e.preventDefault();
  const rating = $('#fodder-rating').value;
  await post('/api/fodder', { prices: { [rating]: +$('#fodder-price').value } });
  $('#fodder-price').value = '';
  toast(`Recorded cheapest ${rating}-rated`);
  loadFodder();
};

$('#player-form').onsubmit = (e) => {
  e.preventDefault();
  const name = $('#player-search').value.trim();
  const p = state.players.find((x) => x.name.toLowerCase() === name.toLowerCase());
  if (!p) return toast('No prices recorded for that card yet — record one below.');
  playerView.id = p.id;
  loadPlayer();
};

$('#player-fetch').onclick = async () => {
  const name = $('#player-search').value.trim();
  if (!name) return toast('Name a card first.');
  toast('Fetching…');
  const res = await post('/api/refresh', { source: 'fut.gg', targets: [name] });
  // The live sources are unverified, so say exactly what went wrong.
  toast(res.ok ? `Recorded ${res.recorded} price(s)` : res.error);
  if (res.ok) refresh();
};

document.querySelectorAll('.viz-range button[data-days]').forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll('.viz-range button[data-days]')
      .forEach((x) => x.classList.remove('active'));
    b.classList.add('active');
    playerView.days = +b.dataset.days;
    loadPlayer();
  };
});

$('#player-table-toggle').onclick = () => {
  playerView.table = !playerView.table;
  $('#player-table-toggle').textContent = playerView.table ? 'Chart' : 'Table';
  loadPlayer();
};

$('#price-form').onsubmit = async (e) => {
  e.preventDefault();
  const rating = $('#price-rating').value;
  const res = await post('/api/prices', {
    name: $('#price-name').value.trim(),
    price: +$('#price-value').value,
    rating: rating ? +rating : null,
  });
  if (res.error) return toast(res.error);
  $('#price-value').value = '';
  toast('Price recorded');
  refresh();
};

$('#fodder-bulk').onsubmit = async (e) => {
  e.preventDefault();
  let parsed;
  try { parsed = JSON.parse($('#fodder-json').value.trim()); }
  catch (err) { return toast('That is not valid JSON.'); }
  const res = await post('/api/fodder', { prices: parsed });
  if (res.error) return toast(res.error);
  $('#fodder-json').value = '';
  toast(`Recorded ${res.recorded} rating bands`);
  refresh();
};

$('#buy-form').onsubmit = async (e) => {
  e.preventDefault();
  const res = await post('/api/trades', {
    name: $('#buy-name').value.trim(),
    buy_price: +$('#buy-price').value,
    method: $('#buy-method').value,
  });
  if (res.error) return toast(res.error);
  $('#buy-price').value = '';
  toast('Buy logged');
  refresh();
};

$('#club-form').onsubmit = async (e) => {
  e.preventDefault();
  const raw = $('#club-json').value.trim();
  if (!raw) return toast('Paste the club JSON first.');
  let parsed;
  try { parsed = JSON.parse(raw); } catch (err) { return toast('That is not valid JSON.'); }
  // An EasySBC stats payload and a raw player list are both accepted;
  // try the stats shape first since it is the documented one.
  let res = await post('/api/easysbc', { payload: parsed });
  if (res.ok) {
    $('#club-json').value = '';
    toast(`Imported ${res.ratings} rating bands, ${res.players} players`);
    return refresh();
  }
  res = await post('/api/club', { payload: parsed });
  if (!res.ok) return toast(res.error || 'Import failed.');
  $('#club-json').value = '';
  toast(`Imported ${res.imported} cards${res.with_prices ? `, ${res.with_prices} with prices` : ''}`);
  refresh();
};

state.platform = $('#platform').value;
refresh();
