// Aperture kit — shared primitives for the PixQuery hi-fi design system.
import React from 'react';
import { AP, STATUS } from './tokens';
import './aperture.css';

export { AP, STATUS };

// small round status dot
export const Dot = ({ c = AP.lumen, size = 7, glow = false }) => (
  <span
    style={{
      display: 'inline-block',
      width: size,
      height: size,
      borderRadius: 99,
      background: c,
      flex: '0 0 auto',
      boxShadow: glow ? `0 0 8px ${c}` : 'none',
    }}
  />
);

// keyboard hint chip — ⌘K
export const Kbd = ({ children }) => (
  <span
    style={{
      fontFamily: AP.mono,
      fontSize: 11,
      color: AP.ink3,
      lineHeight: 1,
      padding: '4px 7px',
      borderRadius: 6,
      background: 'rgba(255,255,255,0.04)',
      border: `1px solid ${AP.line2}`,
      whiteSpace: 'nowrap',
      flex: '0 0 auto',
    }}
  >
    {children}
  </span>
);

export const MagIcon = ({ size = 16, c = AP.ink3 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" style={{ flex: '0 0 auto' }}>
    <circle cx="7" cy="7" r="4.5" stroke={c} strokeWidth="1.6" />
    <line x1="10.5" y1="10.5" x2="14" y2="14" stroke={c} strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);

// ── buttons ──
export const GhostBtn = ({ children, onClick, style = {}, title, disabled, type = 'button' }) => (
  <button
    type={type}
    onClick={onClick}
    title={title}
    disabled={disabled}
    style={{
      fontFamily: AP.sans,
      fontSize: 13,
      fontWeight: 500,
      color: AP.ink2,
      background: 'rgba(255,255,255,0.03)',
      border: `1px solid ${AP.line2}`,
      borderRadius: 9,
      padding: '7px 12px',
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.5 : 1,
      whiteSpace: 'nowrap',
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      transition: 'all .14s',
      ...style,
    }}
    onMouseEnter={(e) => {
      if (disabled) return;
      e.currentTarget.style.background = 'rgba(255,255,255,0.07)';
      e.currentTarget.style.color = AP.ink;
    }}
    onMouseLeave={(e) => {
      e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
      e.currentTarget.style.color = AP.ink2;
    }}
  >
    {children}
  </button>
);

export const LumenBtn = ({ children, onClick, style = {}, disabled, type = 'button' }) => (
  <button
    type={type}
    onClick={onClick}
    disabled={disabled}
    style={{
      fontFamily: AP.sans,
      fontSize: 13,
      fontWeight: 600,
      color: '#fff',
      background: AP.lumenGrad,
      border: 'none',
      borderRadius: 9,
      padding: '8px 16px',
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.55 : 1,
      whiteSpace: 'nowrap',
      display: 'inline-flex',
      alignItems: 'center',
      gap: 7,
      boxShadow: '0 2px 14px rgba(99,102,241,.4)',
      transition: 'transform .12s, box-shadow .14s',
      ...style,
    }}
    onMouseEnter={(e) => {
      if (disabled) return;
      e.currentTarget.style.boxShadow = '0 4px 22px rgba(99,102,241,.6)';
      e.currentTarget.style.transform = 'translateY(-1px)';
    }}
    onMouseLeave={(e) => {
      e.currentTarget.style.boxShadow = '0 2px 14px rgba(99,102,241,.4)';
      e.currentTarget.style.transform = 'none';
    }}
  >
    {children}
  </button>
);

// `tone="danger"` gives it the STATUS.err treatment (icon-only sibling of
// ActBtn's danger tone) for a destructive action in a control cluster.
// `size` scales the square hit target (34 default; 27 for a header cluster,
// 20 for a per-stage inline control) and follows the icon down proportionally
// via `fontSize`/border-radius so small variants don't look like a shrunk
// version of the big one. `spin` rotates the child icon in place (reuses the
// shared `.ap-spin` keyframe) for an in-flight action; combine with
// `active` so a running control reads as lumen-tinted, not neutral.
export const IconBtn = ({ children, onClick, title, active = false, tone, size = 34, spin = false, disabled = false }) => {
  const danger = tone === 'danger';
  const palette = danger
    ? { c: STATUS.err.c, bg: STATUS.err.bg, hoverBg: 'rgba(240,86,107,.24)', line: STATUS.err.line }
    : active
      ? { c: AP.lumenSoft, bg: AP.lumenBg2, hoverBg: AP.lumenBg2, line: AP.lumenLine }
      : { c: AP.ink2, hoverC: AP.ink, bg: 'rgba(255,255,255,0.03)', hoverBg: 'rgba(255,255,255,0.07)', line: AP.line2 };
  const off = !!disabled;
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      disabled={off}
      style={{
        width: size,
        height: size,
        borderRadius: size >= 27 ? 9 : 7,
        cursor: off ? 'not-allowed' : 'pointer',
        flex: '0 0 auto',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: AP.sans,
        fontSize: Math.round(size * 0.44),
        color: palette.c,
        background: palette.bg,
        border: `1px solid ${palette.line}`,
        opacity: off ? 0.55 : 1,
        transition: 'all .14s',
      }}
      onMouseEnter={(e) => {
        if (off) return;
        e.currentTarget.style.background = palette.hoverBg;
        e.currentTarget.style.color = palette.hoverC || palette.c;
      }}
      onMouseLeave={(e) => {
        if (off) return;
        e.currentTarget.style.background = palette.bg;
        e.currentTarget.style.color = palette.c;
      }}
    >
      <span className={spin ? 'ap-spin' : undefined} style={{ display: 'inline-flex' }}>
        {children}
      </span>
    </button>
  );
};

function EyeIcon({ size = 15 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M2.6 12s3.6-6.4 9.4-6.4S21.4 12 21.4 12s-3.6 6.4-9.4 6.4S2.6 12 2.6 12z" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="2.9" stroke="currentColor" strokeWidth="1.9" />
    </svg>
  );
}
function EyeOffIcon({ size = 15 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M4.3 8.4C3.2 9.7 2.6 12 2.6 12s3.6 6.4 9.4 6.4c1.5 0 2.8-.4 3.9-1M9.3 6c.9-.3 1.8-.4 2.7-.4 5.8 0 9.4 6.4 9.4 6.4s-.9 1.7-2.5 3.3" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
      <path d="M4.2 4.2l15.6 15.6" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
    </svg>
  );
}

// Shows/hides something on the page — a pipeline's outputs, one stage's
// body — without persisting anything. Deliberately not built on Toggle: a
// switch (or a checkbox) promises a setting that survives into the next run,
// which this doesn't. `on` is what's currently visible, not a saved value.
// A thin wrapper over IconBtn so the eye affordance is one button, defined
// once, instead of each caller re-picking the icon and re-writing the title.
export const EyeBtn = ({ on, onClick, size = 27, title }) => (
  <IconBtn
    size={size}
    active={on}
    onClick={onClick}
    title={title || (on ? 'Shown on the page — click to hide' : 'Hidden — click to show')}
  >
    {on ? <EyeIcon size={Math.round(size * 0.56)} /> : <EyeOffIcon size={Math.round(size * 0.56)} />}
  </IconBtn>
);

// small ghost action button (Edit / Statistics / Retry rows). `accent` gives
// it the Lumen treatment for the one primary action in a row; `tone="danger"`
// gives it the STATUS.err treatment for a destructive one (Delete) — danger
// wins if both are set. `loading` swaps the button's whole content for a
// spinning icon + `loadingLabel` and forces it disabled: pass a
// present-progressive label ("Retrying…", "Deleting…") so the row reads as
// in-progress rather than just inert. Hover/pressed are hand-rolled via
// direct style mutation (Aperture has no CSS classes for interactive states)
// and reset for free on every re-render since React reconciles `style` back
// onto the node — so a `loading` flip mid-hover snaps to the right look
// without any manual cleanup.
export const ActBtn = ({
  children,
  onClick,
  accent = false,
  tone,
  title,
  disabled,
  loading = false,
  loadingLabel,
}) => {
  const danger = tone === 'danger';
  const off = disabled || loading;
  const palette = danger
    ? { c: STATUS.err.c, bg: STATUS.err.bg, hoverBg: 'rgba(240,86,107,.24)', line: STATUS.err.line, hoverLine: 'rgba(240,86,107,.55)' }
    : accent
      ? { c: AP.lumenSoft, bg: AP.lumenBg, hoverBg: AP.lumenBg2, line: AP.lumenLine, hoverLine: AP.lumenLine }
      : { c: AP.ink2, hoverC: AP.ink, bg: 'rgba(255,255,255,0.03)', hoverBg: 'rgba(255,255,255,0.08)', line: AP.line2, hoverLine: AP.line2 };
  const pressed = {
    bg: danger ? 'rgba(240,86,107,.24)' : accent ? 'rgba(124,108,247,0.3)' : 'rgba(255,255,255,0.13)',
    line: danger ? 'rgba(240,86,107,.55)' : accent ? 'rgba(140,124,247,0.55)' : 'rgba(255,255,255,0.2)',
    c: danger ? STATUS.err.c : accent ? AP.lumenSoft : AP.ink,
  };

  const setHover = (e) => {
    e.currentTarget.style.background = palette.hoverBg;
    e.currentTarget.style.borderColor = palette.hoverLine;
    e.currentTarget.style.color = palette.hoverC || palette.c;
    e.currentTarget.style.transform = 'none';
    e.currentTarget.style.boxShadow = 'none';
  };
  const setRest = (e) => {
    e.currentTarget.style.background = palette.bg;
    e.currentTarget.style.borderColor = palette.line;
    e.currentTarget.style.color = palette.c;
    e.currentTarget.style.transform = 'none';
    e.currentTarget.style.boxShadow = 'none';
  };
  const setPressed = (e) => {
    e.currentTarget.style.background = pressed.bg;
    e.currentTarget.style.borderColor = pressed.line;
    e.currentTarget.style.color = pressed.c;
    e.currentTarget.style.transform = 'translateY(1px)';
    e.currentTarget.style.boxShadow = 'inset 0 1px 3px rgba(0,0,0,.4)';
  };

  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      disabled={off}
      style={{
        fontFamily: AP.sans,
        fontSize: 12.5,
        fontWeight: 600,
        cursor: off ? 'not-allowed' : 'pointer',
        whiteSpace: 'nowrap',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '7px 13px',
        borderRadius: 9,
        transition: 'all .14s',
        opacity: loading ? 0.75 : disabled ? 0.5 : 1,
        color: palette.c,
        background: palette.bg,
        border: `1px solid ${palette.line}`,
        flex: '0 0 auto',
      }}
      onMouseEnter={(e) => !off && setHover(e)}
      onMouseLeave={(e) => !off && setRest(e)}
      onMouseDown={(e) => !off && setPressed(e)}
      onMouseUp={(e) => !off && setHover(e)}
    >
      {loading ? (
        <>
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="ap-spin"
          >
            <path d="M20 12a8 8 0 1 1-2.34-5.66" />
            <path d="M20 4v4.5h-4.5" />
          </svg>
          {loadingLabel}
        </>
      ) : (
        children
      )}
    </button>
  );
};

// pipeline on/off toggle switch
export const Toggle = ({ on, onClick, title }) => (
  <button
    type="button"
    onClick={onClick}
    title={title}
    aria-pressed={on}
    style={{
      width: 36,
      height: 21,
      borderRadius: 99,
      cursor: 'pointer',
      flex: '0 0 auto',
      padding: 2,
      border: 'none',
      position: 'relative',
      transition: 'background .16s',
      background: on ? AP.lumenGrad : 'rgba(255,255,255,0.1)',
      boxShadow: on ? '0 0 12px rgba(124,108,247,.5)' : 'inset 0 0 0 1px rgba(255,255,255,.08)',
    }}
  >
    <span
      style={{
        display: 'block',
        width: 17,
        height: 17,
        borderRadius: 99,
        background: '#fff',
        transform: on ? 'translateX(15px)' : 'translateX(0)',
        transition: 'transform .16s cubic-bezier(.2,.7,.3,1)',
        boxShadow: '0 1px 3px rgba(0,0,0,.4)',
      }}
    />
  </button>
);

// ── Match-reason chip — the signature element. 3 carried styles. ──
export function Chip({ reason, score, variant = 'pill', size = 'md' }) {
  const fs = size === 'sm' ? 11.5 : 12.5;
  if (variant === 'badge') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-start', maxWidth: '90%' }}>
        {score != null && (
          <span
            style={{
              fontFamily: AP.mono,
              fontSize: 11,
              fontWeight: 600,
              color: '#fff',
              background: AP.lumenGrad,
              borderRadius: 6,
              padding: '2px 7px',
              lineHeight: 1.3,
              boxShadow: '0 2px 8px rgba(99,102,241,.55)',
            }}
          >
            {score}
          </span>
        )}
        <span
          style={{
            fontFamily: AP.sans,
            fontSize: 11.5,
            fontWeight: 500,
            color: '#fff',
            background: 'rgba(10,11,18,.6)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            border: '1px solid rgba(255,255,255,.16)',
            borderRadius: 7,
            padding: '3px 8px',
            lineHeight: 1.3,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: '100%',
          }}
        >
          {reason}
        </span>
      </div>
    );
  }
  if (variant === 'underline') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 6, maxWidth: '100%' }}>
        <span
          style={{
            fontFamily: AP.sans,
            fontSize: fs,
            fontWeight: 500,
            color: AP.ink,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            backgroundImage: AP.lumenGrad,
            backgroundRepeat: 'no-repeat',
            backgroundPosition: '0 100%',
            backgroundSize: '100% 2px',
            paddingBottom: 2,
          }}
        >
          {reason}
        </span>
        {score != null && (
          <span style={{ fontFamily: AP.mono, fontSize: fs - 2, fontWeight: 500, color: AP.lumenSoft, flex: '0 0 auto' }}>
            {score}
          </span>
        )}
      </span>
    );
  }
  // pill (default)
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        maxWidth: '100%',
        background: AP.lumenBg,
        border: `1px solid ${AP.lumenLine}`,
        borderRadius: 999,
        padding: '3px 9px 3px 8px',
        lineHeight: 1,
        boxShadow: '0 0 0 1px rgba(124,108,247,.06)',
      }}
    >
      <Dot c={AP.lumen} size={6} glow />
      <span
        style={{
          fontFamily: AP.sans,
          fontSize: fs,
          fontWeight: 500,
          color: AP.lumenSoft,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {reason}
      </span>
      {score != null && (
        <span
          style={{
            fontFamily: AP.mono,
            fontSize: fs - 2.5,
            fontWeight: 500,
            color: AP.lumen,
            opacity: 0.85,
            flex: '0 0 auto',
          }}
        >
          {score}
        </span>
      )}
    </span>
  );
}

// section eyebrow label (mono, faint, tracked)
export const Eyebrow = ({ children, c = AP.ink3, style = {} }) => (
  <span
    style={{
      fontFamily: AP.mono,
      fontSize: 10.5,
      fontWeight: 500,
      letterSpacing: '.09em',
      textTransform: 'uppercase',
      color: c,
      ...style,
    }}
  >
    {children}
  </span>
);

// dropdown-style header control (sort / group)
export const SelectControl = ({ label, value, active = false, accent = false, onClick, title }) => (
  <button
    type="button"
    onClick={onClick}
    title={title}
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 7,
      cursor: 'pointer',
      padding: '6px 11px',
      borderRadius: 9,
      fontFamily: AP.sans,
      transition: 'all .14s',
      background: active ? AP.lumenBg2 : 'rgba(255,255,255,0.03)',
      border: `1px solid ${active ? AP.lumenLine : AP.line2}`,
    }}
    onMouseEnter={(e) => {
      if (!active) e.currentTarget.style.background = 'rgba(255,255,255,0.07)';
    }}
    onMouseLeave={(e) => {
      if (!active) e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
    }}
  >
    <span
      style={{
        fontFamily: AP.mono,
        fontSize: 10,
        letterSpacing: '.06em',
        textTransform: 'uppercase',
        color: active || accent ? AP.lumenSoft : AP.ink3,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
      }}
    >
      {accent && <span style={{ fontSize: 11, color: AP.lumen }}>✦</span>}
      {label}
    </span>
    <span style={{ fontSize: 13, fontWeight: 600, color: active || accent ? '#fff' : AP.ink }}>{value}</span>
    <span style={{ fontSize: 10, color: active || accent ? AP.lumenSoft : AP.ink3 }}>▾</span>
  </button>
);

// health status pill
export function HealthPill({ state = 'ok', label, sm = false }) {
  const s = STATUS[state] || STATUS.idle;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        flex: '0 0 auto',
        background: s.bg,
        border: `1px solid ${s.line}`,
        borderRadius: 99,
        padding: sm ? '2px 8px 2px 7px' : '3px 10px 3px 8px',
      }}
    >
      <Dot c={s.c} size={6} glow={state === 'run'} />
      <span style={{ fontFamily: AP.sans, fontSize: sm ? 11 : 12, fontWeight: 500, color: s.c }}>{label}</span>
    </span>
  );
}

// progress / coverage bar. `pulse` adds a moving sheen for live jobs.
export function Bar({ v = 0.5, c, h = 5, pulse = false, track = 'rgba(255,255,255,0.09)' }) {
  return (
    <span style={{ display: 'block', width: '100%', height: h, borderRadius: 99, background: track, overflow: 'hidden' }}>
      <span
        style={{
          display: 'block',
          height: '100%',
          width: `${Math.round(Math.min(Math.max(v, 0), 1) * 100)}%`,
          borderRadius: 99,
          background: c || AP.lumenGrad,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {pulse && (
          <span
            className="ap-pulse"
            style={{
              position: 'absolute',
              inset: 0,
              background: 'linear-gradient(90deg, transparent, rgba(255,255,255,.5), transparent)',
            }}
          />
        )}
      </span>
    </span>
  );
}

/* Loading placeholder for a value the backend is still computing.
   Sized in the shape of the content it stands in for, so the layout doesn't jump
   when the real thing arrives. */
export const Shimmer = ({ w = '100%', h = 12, r = 6, style = {} }) => (
  <span
    className="ap-shimmer"
    aria-hidden="true"
    style={{ display: 'block', width: w, height: h, borderRadius: r, ...style }}
  />
);

/* A card-shaped cluster of Shimmer lines, standing in for one pipeline output
   while its pipeline is queued or running. */
export const ShimmerCard = ({ lines = 3, label }) => (
  <div
    role="status"
    aria-live="polite"
    aria-label={label || 'Waiting for pipeline output'}
    style={{
      borderRadius: 9,
      border: `1px solid ${AP.line2}`,
      background: 'rgba(255,255,255,0.02)',
      padding: '10px 11px',
      display: 'flex',
      flexDirection: 'column',
      gap: 9,
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
      <Shimmer w={82} h={11} />
      <Shimmer w={54} h={9} />
    </div>
    {Array.from({ length: lines }).map((_, i) => (
      // Last line short, like a paragraph's final line — reads as text, not as bars.
      <Shimmer key={i} w={i === lines - 1 ? '58%' : '100%'} h={10} />
    ))}
  </div>
);

// labeled stat
export const StatBlock = ({ label, value, sub, accent = false }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
    <Eyebrow>{label}</Eyebrow>
    <span
      style={{
        fontFamily: AP.sans,
        fontSize: 19,
        fontWeight: 600,
        color: accent ? AP.lumenSoft : AP.ink,
        lineHeight: 1.1,
      }}
    >
      {value}
    </span>
    {sub && <span style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3 }}>{sub}</span>}
  </div>
);

// circular coverage ring (conic gradient)
export function MetricRing({ v = 0.5, size = 52, label }) {
  const pct = Math.round(Math.min(Math.max(v, 0), 1) * 100);
  return (
    <span
      style={{
        position: 'relative',
        width: size,
        height: size,
        flex: '0 0 auto',
        borderRadius: 99,
        background: `conic-gradient(${AP.lumen} ${pct}%, rgba(255,255,255,0.08) 0)`,
        display: 'inline-block',
      }}
    >
      <span
        style={{
          position: 'absolute',
          inset: 5,
          borderRadius: 99,
          background: AP.card,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
        }}
      >
        <span style={{ fontFamily: AP.mono, fontSize: 12, fontWeight: 600, color: AP.ink }}>{pct}</span>
        {label && (
          <span style={{ fontFamily: AP.mono, fontSize: 7.5, color: AP.ink3, letterSpacing: '.04em' }}>{label}</span>
        )}
      </span>
    </span>
  );
}

// Counter card (pipeline stats)
export function Counter({ label, value, sub, c = AP.ink, accent }) {
  return (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        padding: '15px 16px',
        borderRadius: 13,
        background: AP.card,
        border: `1px solid ${accent ? accent.line : AP.line2}`,
      }}
    >
      <Eyebrow c={accent ? accent.c : AP.ink3}>{label}</Eyebrow>
      <div style={{ fontFamily: AP.sans, fontSize: 25, fontWeight: 600, color: c, lineHeight: 1.15, marginTop: 4 }}>
        {value}
      </div>
      {sub && <div style={{ fontFamily: AP.mono, fontSize: 10.5, color: AP.ink3, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

// photo frame — real thumbnail with Aperture grain + vignette treatment
export function Photo({ src, alt = '', style = {}, badge, children, radius = 12 }) {
  return (
    <div className="ap-photo" style={{ borderRadius: radius, background: AP.cardHi, ...style }}>
      {src && (
        <img
          src={src}
          alt={alt}
          loading="lazy"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
          onError={(e) => {
            e.target.style.display = 'none';
          }}
        />
      )}
      <span className="ap-vig" />
      {badge && <div style={{ position: 'absolute', top: 10, left: 10, zIndex: 2 }}>{badge}</div>}
      {children}
    </div>
  );
}

// ── nav icons (minimal stroke primitives) ──
export const IconSearch = ({ s = 20, c }) => (
  <svg width={s} height={s} viewBox="0 0 20 20" fill="none">
    <circle cx="8.5" cy="8.5" r="5" stroke={c} strokeWidth="1.7" />
    <line x1="12.5" y1="12.5" x2="17" y2="17" stroke={c} strokeWidth="1.7" strokeLinecap="round" />
  </svg>
);
export const IconWorkspaces = ({ s = 20, c }) => (
  <svg width={s} height={s} viewBox="0 0 20 20" fill="none">
    <rect x="2.5" y="2.5" width="6.4" height="6.4" rx="1.6" stroke={c} strokeWidth="1.7" />
    <rect x="11.1" y="2.5" width="6.4" height="6.4" rx="1.6" stroke={c} strokeWidth="1.7" />
    <rect x="2.5" y="11.1" width="6.4" height="6.4" rx="1.6" stroke={c} strokeWidth="1.7" />
    <rect x="11.1" y="11.1" width="6.4" height="6.4" rx="1.6" stroke={c} strokeWidth="1.7" />
  </svg>
);
export const IconPipelines = ({ s = 20, c }) => (
  <svg width={s} height={s} viewBox="0 0 20 20" fill="none">
    <circle cx="4" cy="5" r="2.3" stroke={c} strokeWidth="1.7" />
    <circle cx="4" cy="15" r="2.3" stroke={c} strokeWidth="1.7" />
    <circle cx="16" cy="10" r="2.3" stroke={c} strokeWidth="1.7" />
    <path d="M6.2 5.6 Q11 7 13.8 9.2 M6.2 14.4 Q11 13 13.8 10.8" stroke={c} strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);
export const IconJobs = ({ s = 20, c }) => (
  <svg width={s} height={s} viewBox="0 0 20 20" fill="none">
    <path
      d="M2.5 11.5 H6 L8 6 L11 15 L13 10 H17.5"
      stroke={c}
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

// Control Room header — title + breadcrumb + right actions.
export function ControlHeader({ title, breadcrumb, count, actions, pad = 22 }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 16,
        padding: `20px ${pad}px 18px`,
        borderBottom: `1px solid ${AP.line}`,
        background: AP.panel,
        flex: '0 0 auto',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
        <Eyebrow>{breadcrumb}</Eyebrow>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 11 }}>
          <span style={{ fontFamily: AP.sans, fontSize: 22, fontWeight: 600, letterSpacing: '-0.015em', color: AP.ink }}>
            {title}
          </span>
          {count != null && <span style={{ fontFamily: AP.mono, fontSize: 12, color: AP.ink3 }}>{count}</span>}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, flex: '0 0 auto' }}>{actions}</div>
    </div>
  );
}

// text input in Aperture chrome
export const ApInput = React.forwardRef(function ApInput({ style = {}, ...props }, ref) {
  return (
    <input
      ref={ref}
      {...props}
      style={{
        fontFamily: AP.sans,
        fontSize: 13,
        color: AP.ink,
        background: AP.card,
        border: `1px solid ${AP.line2}`,
        borderRadius: 9,
        padding: '9px 11px',
        outline: 'none',
        width: '100%',
        ...style,
      }}
    />
  );
});

// select in Aperture chrome
export const ApSelect = ({ style = {}, children, ...props }) => (
  <select
    {...props}
    style={{
      fontFamily: AP.sans,
      fontSize: 13,
      color: AP.ink,
      background: AP.card,
      border: `1px solid ${AP.line2}`,
      borderRadius: 9,
      padding: '9px 11px',
      outline: 'none',
      width: '100%',
      ...style,
    }}
  >
    {children}
  </select>
);
