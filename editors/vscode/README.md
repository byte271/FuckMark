# FuckMark: Hidden Unicode Reveal (VS Code / Cursor)

Your editor renders glyphs; attackers hide in the bytes between them. This
extension shows the gap. It highlights hidden or malicious Unicode inline, lists
it in the Problems panel, and strips it on command.

It flags the classes that read as ordinary text but are not:

- **Trojan Source** bidirectional overrides and isolates (CVE-2021-42574)
- zero-width and invisible spacing characters
- Unicode **tag** characters (hidden text / prompt-injection smuggling)
- variation selectors, enclosing marks, line/paragraph separators
- C0/C1 controls, private-use codepoints, and noncharacters

## What you get

- **Inline reveal:** every hidden character gets a red box and a visible
  `‹U+202E›` badge, even when the character itself paints nothing.
- **Problems panel:** each hit is a diagnostic. `critical` (Trojan Source in
  an identifier, comment, or string; tag smuggling) is an Error; `high` and
  other security classes are warnings; the rest are info. Hover text states why
  the character matters. Comment syntax follows the editor language id.
- **Status bar:** a live hidden-character count. Click it to clean the file.
- **Commands** (Command Palette):
  - `FuckMark: Clean hidden Unicode in file`
  - `FuckMark: Clean hidden Unicode in selection`
  - `FuckMark: Toggle hidden-character reveal`
  - `FuckMark: Rescan active file`
- **Clean on save:** set `fuckmark.cleanOnSave` to strip hidden Unicode when
  the file is saved (off by default).

## No dependencies, no build

The extension is plain JavaScript with no runtime dependencies and no compile
step. The scanner (`scan.js`) is a faithful port of FuckMark's
`fuckmark-hidden-scan-v1` engine and is pinned to the Python implementation by
`tests/test_vscode_scanner_parity.py` in the main repository, so the editor and
the CLI agree character for character.

## Run it locally

From this folder:

```text
code --extensionDevelopmentPath="$(pwd)"
```

Or open the folder in VS Code / Cursor and press `F5` to launch an Extension
Development Host. Packaging for the marketplace uses `vsce package`.

## Settings

- `fuckmark.maxFileSize` (default 5,000,000): skip files larger than this.
- `fuckmark.statusBar.alwaysShow` (default true): keep the status item visible on
  clean files.
- `fuckmark.cleanOnSave` (default false): strip hidden Unicode when the file is
  saved.

## Related

- CLI and CI: `fuckmark lint`, the GitHub Action, and the pre-commit hook.
- Library and web API: `fuckmark --scan` / `--clean`, `fuckmark normalize`,
  `POST /api/scan`, `POST /api/guard`, and `POST /api/normalize`.
- Node guard: `guard.js` (`protect`, `extractTagPayload`) matches `fuckmark.protect`.

MIT. Part of [FuckMark](https://github.com/byte271/FuckMark).

