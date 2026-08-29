import "./styles.css";
import {
  DETECT_CONTACT_EMAIL,
  detectFuckMarkInsertions,
  projectVisible,
  removeMarksPayload,
  transformText,
} from "./engine";
import { copyText, mountNav, renderCarriers, stat, toast } from "./ui";

type Mode = "mark" | "unmark";
const HIST_KEY = "fuckmark.web.history.v1";

function currentMode(): Mode {
  const forced = document.body.dataset.mode;
  if (forced === "unmark" || forced === "mark") return forced;
  const params = new URLSearchParams(location.search);
  if (params.get("mode") === "unmark") return "unmark";
  return "mark";
}

function loadHist(): Array<{ text: string; removed?: number; reason: string; ts: number; mode: Mode }> {
  try {
    return JSON.parse(localStorage.getItem(HIST_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHist(list: ReturnType<typeof loadHist>): void {
  localStorage.setItem(HIST_KEY, JSON.stringify(list.slice(0, 20)));
}

function previewOf(text: string): string {
  const clean = projectVisible(text);
  return clean.length > 64 ? clean.slice(0, 64) + "…" : clean;
}

function renderHist(): void {
  const list = document.getElementById("histList");
  const count = document.getElementById("histCount");
  if (!list || !count) return;
  const items = loadHist();
  count.textContent = String(items.length);
  list.replaceChildren();
  for (const item of items) {
    const li = document.createElement("li");
    li.className = "h-item";
    const copy = document.createElement("button");
    copy.className = "btn";
    copy.type = "button";
    copy.textContent = "Copy";
    copy.addEventListener("click", async () => {
      toast((await copyText(item.text)) ? "Copied" : "Copy failed");
    });
    li.innerHTML = `<div><div class="preview"></div><div class="meta"></div></div>`;
    li.querySelector(".preview")!.textContent = previewOf(item.text);
    li.querySelector(".meta")!.textContent = `${item.mode} · ${item.reason} · ${new Date(item.ts).toLocaleString()}`;
    li.appendChild(copy);
    list.appendChild(li);
  }
}

function setMode(mode: Mode): void {
  document.body.dataset.mode = mode;
  const markBtn = document.getElementById("modeMark");
  const unmarkBtn = document.getElementById("modeUnmark");
  markBtn?.classList.toggle("on", mode === "mark");
  unmarkBtn?.classList.toggle("on", mode === "unmark");
  const go = document.getElementById("go");
  const lead = document.getElementById("lead");
  const input = document.getElementById("input") as HTMLTextAreaElement | null;
  if (go) go.textContent = mode === "mark" ? "Insert marks" : "Remove marks";
  if (lead) {
    lead.innerHTML =
      mode === "mark"
        ? "Runs the same five-layer mix as the Python CLI, entirely in this tab. Visible words stay put. URLs, paths, code, and emails are left intact."
        : "Closed-set scan of FuckMark insertion characters only. Not a general AI-watermark detector. A miss is not proof that some other watermark is absent.";
  }
  if (input) {
    input.placeholder = mode === "mark" ? "Paste text to mark…" : "Paste text to scan for FuckMark insertions…";
  }
  mountNav(mode);
}

function renderStatus(nodes: HTMLElement[]): void {
  const box = document.getElementById("status");
  if (!box) return;
  box.replaceChildren(...nodes);
}

async function run(): Promise<void> {
  const input = document.getElementById("input") as HTMLTextAreaElement;
  const view = document.getElementById("view");
  const src = input.value;
  const mode = (document.body.dataset.mode as Mode) || "mark";
  if (mode === "mark") {
    const result = transformText(src);
    renderStatus([
      stat("processed", result.change_count > 0 ? "yes" : "no", result.change_count > 0 ? "ok" : "warn"),
      stat("reason", result.reason, result.change_count > 0 ? "ok" : "warn"),
      stat("insertions", String(result.change_count), result.change_count > 0 ? "ok" : ""),
      stat("sites", String(result.site_count)),
      stat("last_index", result.last_source_index == null ? "" : String(result.last_source_index)),
      stat("capped", result.capped ? "yes" : "no", result.capped ? "warn" : ""),
      stat("first_unsupported", result.first_unsupported),
      stat("source_length", String(result.source_length)),
    ]);
    if (view) view.innerHTML = renderCarriers(result.output_text);
    const ok = await copyText(result.output_text);
    toast(
      result.change_count > 0
        ? ok
          ? "Marked text copied"
          : "Marked, copy failed"
        : `Unchanged (${result.reason})`,
    );
    if (result.change_count > 0) {
      saveHist([{ text: result.output_text, reason: result.reason, ts: Date.now(), mode }, ...loadHist()]);
      renderHist();
    }
    return;
  }
  const payload = removeMarksPayload(src);
  const detect = detectFuckMarkInsertions(src);
  if (!src) {
    renderStatus([stat("local scan", "no input", "warn"), stat("found", "0")]);
    if (view) view.innerHTML = "";
    toast("Paste text first");
    return;
  }
  if (!payload.ok) {
    renderStatus([
      stat("local scan", "not detected", "warn"),
      stat("found", "0"),
      stat("contact", DETECT_CONTACT_EMAIL),
    ]);
    if (view) view.innerHTML = renderCarriers(src);
    const miss = document.getElementById("miss");
    if (miss) miss.hidden = false;
    return;
  }
  const miss = document.getElementById("miss");
  if (miss) miss.hidden = true;
  renderStatus([
    stat("local scan", "detected", "ok"),
    stat("found", String(detect.found), "ok"),
    stat("mark", String(detect.mark)),
    stat("cc", String(detect.cc)),
    stat("me", String(detect.me)),
    stat("cf", String(detect.cf)),
    stat("ia", String(detect.ia)),
    stat("first", detect.first),
    stat("removed", String(payload.removed), "ok"),
  ]);
  if (view) view.innerHTML = renderCarriers(payload.text);
  const ok = await copyText(payload.text);
  toast(ok ? "Cleaned text copied" : "Stripped, copy failed");
  saveHist([{ text: payload.text, removed: payload.removed, reason: "stripped", ts: Date.now(), mode }, ...loadHist()]);
  renderHist();
}

function metaIn(): void {
  const input = document.getElementById("input") as HTMLTextAreaElement;
  const meta = document.getElementById("inMeta");
  if (!meta) return;
  const n = [...input.value].length;
  meta.textContent = n + (n === 1 ? " char" : " chars");
}

function main(): void {
  const mode = currentMode();
  setMode(mode);
  document.getElementById("modeMark")?.addEventListener("click", () => {
    history.replaceState(null, "", "./");
    setMode("mark");
  });
  document.getElementById("modeUnmark")?.addEventListener("click", () => {
    history.replaceState(null, "", "./mark.html");
    setMode("unmark");
  });
  document.getElementById("go")?.addEventListener("click", () => void run());
  document.getElementById("input")?.addEventListener("input", metaIn);
  document.getElementById("clearHist")?.addEventListener("click", () => {
    saveHist([]);
    renderHist();
    toast("History cleared");
  });
  document.getElementById("sample")?.addEventListener("click", () => {
    const input = document.getElementById("input") as HTMLTextAreaElement;
    input.value = "I do not agree.\nSee https://example.com/a and src/main.py.";
    metaIn();
  });
  metaIn();
  renderHist();
}

main();
