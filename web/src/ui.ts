export const STAR_SVG = `<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 1.6 14.4 8.4 21.6 9.2 16.2 14.1 17.8 21.2 12 17.6 6.2 21.2 7.8 14.1 2.4 9.2 9.6 8.4Z"/></svg>`;

export function mountNav(active: "mark" | "unmark" | "demo" | "limits"): void {
  const nav = document.getElementById("nav");
  if (!nav) return;
  nav.innerHTML = `
    <a class="brand" href="./">${STAR_SVG}<span>FuckMark</span></a>
    <div class="links">
      <a href="./" class="${active === "mark" ? "active" : ""}">Mark</a>
      <a href="./mark.html" class="${active === "unmark" ? "active" : ""}">Unmark</a>
      <a href="./demo.html" class="${active === "demo" ? "active" : ""}">Demo</a>
      <a href="./limits.html" class="${active === "limits" ? "active" : ""}">Limits</a>
    </div>
  `;
}

export function hex(code: number): string {
  return "U+" + code.toString(16).toUpperCase().padStart(4, "0");
}

export function renderCarriers(text: string): string {
  let html = "";
  for (const ch of text) {
    const cp = ch.codePointAt(0)!;
    if (cp === 0x034f) {
      html += '<span class="cgj" title="U+034F">[034F]</span>';
      continue;
    }
    if (cp === 0xfe00) {
      html += '<span class="vs" title="U+FE00">[FE00]</span>';
      continue;
    }
    if (cp === 0x7f || (cp >= 0x80 && cp <= 0x84) || (cp >= 0x86 && cp <= 0x9f)) {
      html += `<span class="cc" title="${hex(cp)}">[${hex(cp).slice(2)}]</span>`;
      continue;
    }
    if (cp === 0x20dd) {
      html += '<span class="me" title="U+20DD">[20DD]</span>';
      continue;
    }
    if (cp >= 0x13430 && cp <= 0x13438) {
      html += `<span class="cf" title="${hex(cp)}">[${hex(cp).slice(2)}]</span>`;
      continue;
    }
    if (cp >= 0xfff9 && cp <= 0xfffb) {
      html += `<span class="ia" title="${hex(cp)}">[${hex(cp).slice(2)}]</span>`;
      continue;
    }
    const shown = ch === "\n" ? "\\n" : ch === "\r" ? "\\r" : ch === "\t" ? "\\t" : escapeHtml(ch);
    html += shown;
  }
  return html || '<span style="color:var(--mute)">(empty)</span>';
}

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]!));
}

export function toast(message: string): void {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = message;
  el.classList.add("on");
  window.setTimeout(() => el.classList.remove("on"), 1600);
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      const ok = document.execCommand("copy");
      area.remove();
      return ok;
    } catch {
      return false;
    }
  }
}

export function stat(label: string, value: string, tone = ""): HTMLElement {
  const el = document.createElement("div");
  el.className = "stat";
  el.innerHTML = `<div class="k">${escapeHtml(label)}</div><div class="v${tone ? " " + tone : ""}">${escapeHtml(value)}</div>`;
  return el;
}
