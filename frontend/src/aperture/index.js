// Aperture — PixQuery's design system. Single entry point re-exporting every
// public primitive (kit.js) and composed block (blocks.js). Existing app code
// keeps importing directly from './kit' / './blocks' / './tokens'; this file
// exists as the one place that names the whole public surface at once.
export * from './kit';
export * from './blocks';
