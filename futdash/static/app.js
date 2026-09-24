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

async function loadPlayers() {
  state.players = await get('/api/players');
  $('#player-list').innerHTML = state.players
    .map((p) => `<option value="${p.name}">`).join('');
}

async function refresh() {
  await Promise.all([loadStats(), loadPlayers()]);
  const tab = document.querySelector('nav button.active').dataset.tab;
  await ({ market: loadMarket, snipe: loadSnipe, fodder: loadFodder,
    holdings: loadHoldings, journal: loadJournal }[tab])();
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

state.platform = $('#platform').value;
refresh();
