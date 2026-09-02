# FuckMark browser extension (Chromium)

Reveal hidden Unicode on the page you are reading. The classifier is
`fuckmark-hidden-scan-v1`. The popup prefers the WASM build
(`fuckmark_scan.wasm`) when it can fetch it, and `scan.js` is a
byte-for-byte copy of the VS Code port as the fallback. On-page reveal
and paste-safe stay on `scan.js` so they stay synchronous. Nothing is
uploaded.

It flags:

- **Trojan Source** bidirectional overrides and isolates (CVE-2021-42574)
- zero-width and invisible spacing characters
- Unicode **tag** characters (hidden text / prompt-injection smuggling)
- C0/C1 controls, noncharacters, and lone surrogates

Emoji ZWJ sequences stay intact when **both** neighbors are emoji (or a
variation selector). A ZWJ next to ordinary letters is stripped.

## Load it unpacked

Chrome, Edge, Brave, or Arc:

1. Open `chrome://extensions` (or `edge://extensions`).
2. Enable **Developer mode**.
3. **Load unpacked** and choose this folder (`editors/browser`).

The toolbar button opens the popup. Right-click a page for scan / reveal /
scan-selection.

## What you get

- **Popup:** paste text, copy security-clean text, or fix Trojan Source (bidi
  only). **Scan this page** counts hidden characters in visible text nodes.
  **Reveal** paints `U+XXXX` badges and a highlight on those characters.
- **Paste-safe:** when enabled, a paste into an input or contenteditable field
  is rewritten to drop hidden Unicode before it lands. Off by default.
- **Context menu:** scan this page, reveal, hide, or send the selection to the
  popup.
- **Badge:** after a scan or reveal, the toolbar icon shows the finding count.

`chrome://` pages, the Web Store, and other extension pages cannot be scanned.
The content script runs on `http://` and `https://` only.

## Permissions

- `storage` — paste-safe preference
- `contextMenus` — right-click actions
- `activeTab` — talk to the page you invoked the action on

The content script is injected on ordinary web pages so reveal and paste-safe
can run locally. Text never leaves the machine.

## Related

- CLI and CI: `fuckmark --scan`, `fuckmark lint`, the GitHub Action
- Local page: `fuckmark web` then `/scan.html`
- Editor: `editors/vscode`

MIT. Part of [FuckMark](https://github.com/byte271/FuckMark).
