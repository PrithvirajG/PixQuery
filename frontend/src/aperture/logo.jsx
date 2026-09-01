// The canonical PixQuery mark + lockups — a bracket-cornered pixel grid, with
// an optional wordmark. Ported from the brand spec authored in Claude Design
// (a <pixquery-logo> web component) into a plain React component so it shares
// this repo's rendering path instead of a second, parallel one.
//
// variant: 'horizontal' (default, mark + wordmark side by side) | 'stacked'
//   (mark above wordmark) | 'mark' (icon only — nav rails, favicons, app tiles).
// size: the mark's height in px (the wordmark scales off it). Default 32.
// theme: 'brand' (violet gradient mark, white wordmark — the dark canvas) |
//   'light' (dark wordmark, for light backgrounds) | 'mono' (inherits
//   currentColor throughout, for single-colour contexts like a filled tile).
import React, { useId } from 'react';
import { AP } from './tokens';

// The mark's own gradient. Deliberately its own constants, not AP.lumen/
// AP.lumenGrad (the UI's Lumen accent on buttons, badges, pills) — keeping
// them distinct means re-tuning one can never silently redraw the other.
export const BRAND = {
  light: '#A78BFA',
  dark: '#6D4AFF',
  solid: '#8B5CF6',
};

function Mark({ mono, gradientId }) {
  const stroke = mono ? 'currentColor' : `url(#${gradientId})`;
  const fill = (hex) => (mono ? 'currentColor' : hex);
  return (
    <svg viewBox="0 0 48 48" fill="none" width="100%" height="100%" role="img" aria-hidden="true">
      {!mono && (
        <defs>
          <linearGradient id={gradientId} x1="8" y1="40" x2="40" y2="8" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor={BRAND.light} />
            <stop offset="1" stopColor={BRAND.dark} />
          </linearGradient>
        </defs>
      )}
      {/* corner brackets — the "frame" the pixel grid sits inside */}
      <path d="M15 9H11.5A2.5 2.5 0 0 0 9 11.5V15" stroke={stroke} strokeWidth="3.2" strokeLinecap="round" />
      <path d="M33 9h3.5A2.5 2.5 0 0 1 39 11.5V15" stroke={stroke} strokeWidth="3.2" strokeLinecap="round" />
      <path d="M15 39h-3.5A2.5 2.5 0 0 1 9 36.5V33" stroke={stroke} strokeWidth="3.2" strokeLinecap="round" />
      <path d="M33 39h3.5a2.5 2.5 0 0 0 2.5-2.5V33" stroke={stroke} strokeWidth="3.2" strokeLinecap="round" />
      {/* the pixel grid — a photo mid-scan */}
      <rect x="21" y="15" width="5" height="5" rx=".8" fill={fill('#A78BFA')} />
      <rect x="28" y="15" width="4" height="4" rx=".7" fill={fill('#8B5CF6')} />
      <rect x="17" y="21" width="5" height="5" rx=".8" fill={fill('#8B5CF6')} />
      <rect x="24" y="21" width="6" height="6" rx=".9" fill={fill('#A78BFA')} />
      <rect x="20" y="28" width="5" height="5" rx=".8" fill={fill('#7C5CFF')} />
      <rect x="27" y="28" width="5" height="5" rx=".8" fill={fill('#6D4AFF')} />
      <rect x="13" y="25" width="3" height="3" rx=".6" fill={fill('#8B5CF6')} opacity=".9" />
      <rect x="31" y="22" width="3" height="3" rx=".6" fill={fill('#7C5CFF')} opacity=".75" />
      <rect x="34" y="17" width="2.5" height="2.5" rx=".5" fill={fill('#8B5CF6')} opacity=".55" />
    </svg>
  );
}

export function Logo({ variant = 'horizontal', size = 32, theme = 'brand' }) {
  // Scopes the gradient id to this instance — two logos on one page must not
  // collide over one <linearGradient id>.
  const gradientId = useId();
  const mono = theme === 'mono';
  const pix = mono ? 'currentColor' : theme === 'light' ? '#0B0D15' : '#FFFFFF';
  const qry = mono ? 'currentColor' : BRAND.solid;
  const stacked = variant === 'stacked';
  const fontSize = stacked ? size * 0.5 : size * 0.72;
  return (
    <span
      // The wordmark's two-tone "Pix"/"Query" styling splits the text across
      // nested spans, which the SVG mark (aria-hidden) contributes nothing to
      // either — without an explicit label this lockup has no accessible name
      // at all, in every variant including icon-only nav/favicon usage. A
      // bare `aria-label` on a role-less <span> (role "generic") is silently
      // ignored by the accessibility tree — ARIA prohibits author-provided
      // names on that role — so this needs an explicit naming-capable role.
      role="img"
      aria-label="PixQuery"
      data-testid="pixquery-logo"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        lineHeight: 1,
        color: 'inherit',
        flexDirection: stacked ? 'column' : 'row',
        gap: stacked ? size * 0.18 : size * 0.28,
      }}
    >
      <span style={{ width: size, height: size, display: 'block', flex: '0 0 auto' }}>
        <Mark mono={mono} gradientId={gradientId} />
      </span>
      {variant !== 'mark' && (
        <span
          style={{
            fontFamily: AP.sans,
            fontWeight: 500,
            fontSize,
            letterSpacing: '-0.025em',
            whiteSpace: 'nowrap',
            color: pix,
          }}
        >
          Pix<span style={{ color: qry }}>Query</span>
        </span>
      )}
    </span>
  );
}
