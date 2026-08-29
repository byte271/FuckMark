# FuckMark static website

This folder is a Vite + TypeScript port of the **product** CLI:

- insert the live five-layer mix (`transform_text` / `apply_letter_alternating_mix`)
- detect FuckMark carriers (`detect_fuckmark_insertions`)
- strip them (`project_visible_v1`)
- skip URLs, paths, emails, code, and the other hard-machine spans

It is a complete static site. There is no application server. `npm run build` writes files you can drop on GitHub Pages, Netlify, Cloudflare Pages, or any object store.

Research tooling (GPT-2, HuggingFace, SynthID adapters) stays in Python. This package does not load those models and does not claim a general watermark-removal result.

## Pages

| File | Role |
| --- | --- |
| `index.html` | Mark (insert) |
| `mark.html` | Unmark (detect + strip), same URL as the old paste tool |
| `demo.html` | Live samples + frozen Gate v2 table |
| `limits.html` | Honest limits |
| `public/rec.html` | Existing `go.txt` gate |

## Develop

Node 20+. From this directory:

```text
npm install
npm test
npm run dev
```

`npm test` checks the TypeScript engine against goldens produced by the Python CLI (`src/engine/generated/fixtures.json`).

Regenerate goldens after a product-engine change:

```text
npm run gen:unicode
npm run gen:fixtures
```

`gen:fixtures` imports the repository `fuckmark` package, so run it from a checkout that can `import fuckmark`.

## Deploy

```text
npm run build
```

Upload `dist/`:

- **GitHub Pages:** workflow [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) (workflow_dispatch or push to `main`). Custom domain file is `public/CNAME` → `mark.q1z.org`.
- **Netlify / Cloudflare Pages:** build command `npm ci && npm run build` in `web/`, publish directory `web/dist` (or this folder’s `dist` if the project root is `web/`).
- **Manual copy to mark.q1z.org:** replace the previous static HTML with `dist/` contents. Repository CI still cannot SSH to that host by itself.

`base` is `./`, so the site also works from a subpath or `file://` for the HTML shell (module URLs from `file://` still need a local static server).

## What is not ported

- `fuckmark web` still serves the packaged Python `mark.html` plus `/api/remove-marks`.
- Cycle 8 measurement, tokenizers, and detector calibration remain Python.
