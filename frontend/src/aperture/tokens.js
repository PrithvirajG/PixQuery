// Aperture design tokens — PixQuery hi-fi design system.
// Dark Carbon canvas · Lumen violet→indigo intelligence glow · Ember human accent ·
// photographs as the light source · Geist / Geist Mono type.

export const AP = {
  // ── Carbon surfaces (cool near-black) ──
  void: '#06070d', // deepest — behind everything
  base: '#0b0d15', // app background
  panel: '#11131d', // rails / bars
  card: '#171a26', // elevated cards / chips
  cardHi: '#1d2130', // hover / raised
  line: 'rgba(255,255,255,0.07)',
  line2: 'rgba(255,255,255,0.13)',
  // ── Ink ──
  ink: '#edeff7',
  ink2: '#a4a9bd',
  ink3: '#6c7286',
  ink4: '#474d61',
  // ── Lumen — the intelligence accent (violet → indigo) ──
  lumen: '#8b7bf7',
  lumen2: '#6366f1',
  lumenSoft: '#bcb3fc',
  lumenBg: 'rgba(124,108,247,0.13)',
  lumenBg2: 'rgba(124,108,247,0.22)',
  lumenLine: 'rgba(140,124,247,0.42)',
  lumenGrad: 'linear-gradient(135deg, #8b7bf7 0%, #6366f1 100%)',
  // ── Ember — rare human / memory accent ──
  ember: '#ef9355',
  emberBg: 'rgba(239,147,85,0.15)',
  emberLine: 'rgba(239,147,85,0.45)',
  // ── Type ──
  sans: "'Geist', 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif",
  mono: "'Geist Mono', ui-monospace, 'SF Mono', Menlo, monospace",
};

// ── status palette (cool greens/reds tuned to Carbon) ──
export const STATUS = {
  ok: { c: '#46d6a6', bg: 'rgba(70,214,166,.13)', line: 'rgba(70,214,166,.4)' },
  warn: { c: AP.ember, bg: AP.emberBg, line: AP.emberLine },
  err: { c: '#f0566b', bg: 'rgba(240,86,107,.14)', line: 'rgba(240,86,107,.42)' },
  run: { c: AP.lumen, bg: AP.lumenBg, line: AP.lumenLine },
  queue: { c: AP.ink2, bg: 'rgba(255,255,255,.04)', line: AP.line2 },
  idle: { c: AP.ink3, bg: 'rgba(255,255,255,.04)', line: AP.line2 },
};
