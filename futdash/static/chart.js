'use strict';

/* Price history chart.
 *
 * One series -- a single card's price over time -- so there is no legend;
 * the panel heading names the card. A crosshair finds the date, because
 * nobody can reliably aim at a 2px line, and the tooltip leads with the
 * number since the reader already knows which card they are looking at.
 *
 * A table view sits behind a toggle so the data is reachable without
 * hovering, and without colour.
 */

const CHART = {
  padL: 58, padR: 14, padT: 14, padB: 26,
  height: 220,
  dotR: 4,
};

const fmtCoins = (n) => Math.round(n).toLocaleString();
const fmtDay = (iso) => {
  const d = new Date(iso);
  return isNaN(d) ? String(iso).slice(0, 10)
    : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
};

/** Round a range outward to readable tick values. */
function ticks(min, max, count = 4) {
  if (min === max) return [min];
  const raw = (max - min) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  // Fine-grained multipliers: with only [1,2,2.5,5,10] a raw step just over
  // the decade (say 10,150) jumps straight to 20,000 and leaves a wide
  // range with two gridlines on it.
  const step = [1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10]
    .map((m) => m * mag).find((s) => s >= raw) || mag * 10;
  const out = [];
  for (let v = Math.ceil(min / step) * step; v <= max; v += step) out.push(v);
  return out.length ? out : [min, max];
}

function svgEl(name, attrs = {}) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', name);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

/**
 * Render a price history chart into `mount`.
 * points: [{ts, price}], oldest first.
 */
function priceChart(mount, points, opts = {}) {
  mount.textContent = '';
  if (!points || points.length < 2) {
    const p = document.createElement('p');
    p.className = 'empty';
    p.textContent = points && points.length
      ? 'Only one price recorded — no history to plot yet.'
      : 'No price history for this card yet.';
    mount.appendChild(p);
    return;
  }

  const w = Math.max(mount.clientWidth || 640, 320);
  const h = CHART.height;
  const { padL, padR, padT, padB } = CHART;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;

  const prices = points.map((p) => p.price);
  let lo = Math.min(...prices), hi = Math.max(...prices);
  if (lo === hi) { lo = lo * 0.95; hi = hi * 1.05; }
  // A little headroom so the line never rides the frame.
  const pad = (hi - lo) * 0.08;
  lo -= pad; hi += pad;

  const x = (i) => padL + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const y = (v) => padT + innerH - ((v - lo) / (hi - lo)) * innerH;

  const svg = svgEl('svg', {
    viewBox: `0 0 ${w} ${h}`, width: '100%', height: h,
    role: 'img', 'aria-label': opts.label || 'Price history',
  });
  svg.style.display = 'block';
  svg.style.overflow = 'visible';

  // --- grid + y axis (recessive) -------------------------------------
  for (const t of ticks(lo, hi)) {
    svg.appendChild(svgEl('line', {
      x1: padL, x2: w - padR, y1: y(t), y2: y(t),
      stroke: 'var(--viz-grid)', 'stroke-width': 1,
    }));
    const lbl = svgEl('text', {
      x: padL - 8, y: y(t) + 4, 'text-anchor': 'end',
      fill: 'var(--viz-text-muted)', 'font-size': 11,
    });
    lbl.textContent = fmtCoins(t);
    svg.appendChild(lbl);
  }

  // --- x labels: first, middle, last ---------------------------------
  for (const i of [0, Math.floor((points.length - 1) / 2), points.length - 1]) {
    const lbl = svgEl('text', {
      x: x(i), y: h - 6,
      'text-anchor': i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle',
      fill: 'var(--viz-text-muted)', 'font-size': 11,
    });
    lbl.textContent = fmtDay(points[i].ts);
    svg.appendChild(lbl);
  }

  // --- the line ------------------------------------------------------
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.price).toFixed(1)}`).join(' ');
  svg.appendChild(svgEl('path', {
    d, fill: 'none', stroke: 'var(--viz-series-1)',
    'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round',
  }));

  // --- crosshair + hover dot (hidden until pointed at) ---------------
  const hair = svgEl('line', {
    y1: padT, y2: padT + innerH, stroke: 'var(--viz-text-muted)',
    'stroke-width': 1, 'stroke-dasharray': '3 3', opacity: 0,
  });
  svg.appendChild(hair);
  const dot = svgEl('circle', {
    r: CHART.dotR, fill: 'var(--viz-series-1)',
    stroke: 'var(--viz-surface)', 'stroke-width': 2, opacity: 0,
  });
  svg.appendChild(dot);

  const tip = document.createElement('div');
  tip.className = 'viz-tip hidden';
  mount.appendChild(tip);
  mount.appendChild(svg);

  const nearest = (clientX) => {
    const box = svg.getBoundingClientRect();
    const px = ((clientX - box.left) / box.width) * w;
    let best = 0, bestD = Infinity;
    points.forEach((_, i) => {
      const dx = Math.abs(x(i) - px);
      if (dx < bestD) { bestD = dx; best = i; }
    });
    return best;
  };

  const show = (evt) => {
    const i = nearest(evt.clientX);
    const p = points[i];
    hair.setAttribute('x1', x(i));
    hair.setAttribute('x2', x(i));
    hair.setAttribute('opacity', 1);
    dot.setAttribute('cx', x(i));
    dot.setAttribute('cy', y(p.price));
    dot.setAttribute('opacity', 1);

    // Values lead, labels follow. Untrusted text goes in as text, never HTML.
    tip.textContent = '';
    const v = document.createElement('div');
    v.className = 'viz-tip-value';
    v.textContent = fmtCoins(p.price) + ' coins';
    const l = document.createElement('div');
    l.className = 'viz-tip-label';
    l.textContent = fmtDay(p.ts) + (p.source ? ` · ${p.source}` : '');
    tip.append(v, l);
    tip.classList.remove('hidden');

    const box = svg.getBoundingClientRect();
    const left = (x(i) / w) * box.width;
    tip.style.left = `${Math.min(Math.max(left, 60), box.width - 60)}px`;
    tip.style.top = `${(y(p.price) / h) * box.height - 8}px`;
  };
  const hide = () => {
    hair.setAttribute('opacity', 0);
    dot.setAttribute('opacity', 0);
    tip.classList.add('hidden');
  };

  svg.addEventListener('pointermove', show);
  svg.addEventListener('pointerleave', hide);
}

/** The table behind the chart — reachable without hovering or colour. */
function priceTable(points) {
  if (!points || !points.length) return '<p class="empty">Nothing to show.</p>';
  const rows = [...points].reverse().map((p) => {
    const tr = document.createElement('tr');
    const td1 = document.createElement('td');
    td1.textContent = String(p.ts).slice(0, 16).replace('T', ' ');
    const td2 = document.createElement('td');
    td2.className = 'num';
    td2.textContent = fmtCoins(p.price);
    const td3 = document.createElement('td');
    td3.className = 'sub';
    td3.textContent = p.source || '';
    tr.append(td1, td2, td3);
    return tr.outerHTML;
  }).join('');
  return `<table><thead><tr><th>When</th><th class="num">Price</th><th>Source</th></tr></thead><tbody>${rows}</tbody></table>`;
}

window.futdashChart = { priceChart, priceTable };
