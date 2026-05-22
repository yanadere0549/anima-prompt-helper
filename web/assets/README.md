# anima-prompt-helper — SVG Assets

## Files

| File | viewBox | Purpose |
|---|---|---|
| `icon.svg` | 32×32 | Primary icon for dark themes. Used in tab strip, node title bar, browser favicons. Readable at 16×16. |
| `icon-light.svg` | 32×32 | Same composition as `icon.svg` but with a light (`#eef2ff`) background and deeper-contrast strokes — for light-themed UIs. |
| `logo.svg` | 256×64 | Horizontal lockup: icon on left + two-line wordmark ("anima" / "-prompt-helper") on right. For splash screens, about panels, or documentation headers. |

## Design

All three files share the same visual language:
- **Bracket pair `[ ]`** in aqua/teal (`#22d3ee`) — represents tag/prompt composition.
- **4-point sparkle star** in soft pink (`#f472b6`) — evokes "best quality" anime aesthetic.
- **Three palette dots** (indigo `#6366f1`, teal `#22d3ee`, pink `#f472b6`) — hints at color/style selection.
- Dark indigo (`#1e1b4b`) background for dark-theme variants.

## Extension Wiring

The icon files are available for use by `web/extensions/anima_prompt_helper.js`.
To reference the icon from the JS extension, use a path relative to the ComfyUI web root, e.g.:

```js
const ICON_URL = new URL("../assets/icon.svg", import.meta.url).href;
```

This wiring is **available for future use** — no automatic injection is performed by these asset files themselves.
