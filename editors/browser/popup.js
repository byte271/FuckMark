"use strict";

const input = document.getElementById("input");
const summary = document.getElementById("summary");
const findingsEl = document.getElementById("findings");
const pasteSafe = document.getElementById("pasteSafe");
const scanPage = document.getElementById("scanPage");
const revealPage = document.getElementById("revealPage");
const hidePage = document.getElementById("hidePage");
const copyClean = document.getElementById("copyClean");
const fixTrojan = document.getElementById("fixTrojan");
const examplesEl = document.getElementById("examples");

const RLO = String.fromCodePoint(0x202E);
const PDF = String.fromCodePoint(0x202C);
const EXAMPLES = [
  { label: "Trojan Source", text: "if (accessLevel != " + RLO + "admin" + PDF + ") {" },
  { label: "Commenting-out", text: "// " + RLO + " return;" },
  { label: "Tag smuggling", text: "Approve this request." + String.fromCodePoint(0xE0061, 0xE0062) },
];

function hasChromeTabs() {
  return typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.query;
}

function pageApi() {
  return globalThis.FuckMarkPage;
}

function scanApi() {
  return pageApi().getScan();
}

async function sendToActive(payload) {
  if (!hasChromeTabs()) return { ok: false, reason: "no-chrome" };
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tab = tabs && tabs[0];
  if (!tab || tab.id == null) return { ok: false, reason: "no-tab" };
  try {
    return await chrome.tabs.sendMessage(tab.id, payload);
  } catch (_err) {
    return { ok: false, reason: "no-content-script" };
  }
}

function renderLocal() {
  const text = input.value;
  const result = scanApi().scanText(text, null, "auto");
  const highest = pageApi().highestSeverity(result.findings);
  if (!text) {
    summary.textContent = "Paste text or scan the page.";
    findingsEl.replaceChildren();
    copyClean.disabled = true;
    fixTrojan.disabled = true;
    return;
  }
  copyClean.disabled = false;
  fixTrojan.disabled = !result.findings.some((item) => item.category === "bidi_control");
  if (result.total === 0) {
    summary.innerHTML = "No hidden characters in <strong>" + text.length + "</strong> code units.";
  } else {
    const sev = highest ? " Highest severity: <strong>" + highest + "</strong>." : "";
    summary.innerHTML = "Found <strong>" + result.total + "</strong> hidden character" + (result.total === 1 ? "" : "s") + "." + sev;
  }
  findingsEl.replaceChildren(...result.findings.slice(0, 12).map(findingCard));
}

function findingCard(finding) {
  const item = document.createElement("li");
  const header = document.createElement("header");
  const code = document.createElement("span");
  code.textContent = scanApi().codepointToken(finding.codepoint);
  const sev = document.createElement("span");
  sev.className = "hit sev-" + (finding.severity || "medium");
  sev.textContent = finding.severity || "medium";
  const meta = document.createElement("span");
  meta.textContent = finding.category + " / " + finding.context;
  header.append(code, sev, meta);
  const why = document.createElement("p");
  why.textContent = finding.why || "";
  item.append(header, why);
  return item;
}

async function copyText(value) {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch (_err) {
    return false;
  }
}

function pageStatus(result, verb) {
  if (!result || !result.ok) {
    summary.textContent =
      result && result.reason === "no-content-script"
        ? "This page cannot be scanned (browser UI or missing content script)."
        : "Could not " + verb + " this page.";
    return;
  }
  if (!result.total) {
    summary.innerHTML = "No hidden characters on this page.";
    return;
  }
  const sev = result.highest ? " Highest severity: <strong>" + result.highest + "</strong>." : "";
  summary.innerHTML = "Page has <strong>" + result.total + "</strong> hidden character" + (result.total === 1 ? "" : "s") + "." + sev;
}

input.addEventListener("input", renderLocal);
EXAMPLES.forEach((example) => {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = example.label;
  button.addEventListener("click", () => {
    input.value = example.text;
    renderLocal();
  });
  examplesEl.append(button);
});
copyClean.addEventListener("click", async () => {
  const cleaned = pageApi().cleanForPaste(input.value).cleaned;
  const ok = await copyText(cleaned);
  summary.textContent = ok ? "Copied security-clean text (emoji sequences kept)." : "Could not copy.";
});
fixTrojan.addEventListener("click", async () => {
  const fixed = scanApi().autofixTrojanSource(input.value);
  input.value = fixed.cleaned;
  renderLocal();
  const ok = await copyText(fixed.cleaned);
  summary.textContent = ok
    ? "Stripped " + fixed.removed + " bidi control" + (fixed.removed === 1 ? "" : "s") + " and copied the result."
    : "Stripped " + fixed.removed + " bidi control" + (fixed.removed === 1 ? "" : "s") + ".";
});
scanPage.addEventListener("click", async () => {
  pageStatus(await sendToActive({ type: "scan" }), "scan");
});
revealPage.addEventListener("click", async () => {
  pageStatus(await sendToActive({ type: "reveal" }), "reveal");
});
hidePage.addEventListener("click", async () => {
  const result = await sendToActive({ type: "hide" });
  summary.textContent = result && result.ok ? "Reveal hidden." : "Could not hide reveal.";
});
pasteSafe.addEventListener("change", async () => {
  const enabled = pasteSafe.checked;
  if (typeof chrome !== "undefined" && chrome.storage) {
    await chrome.storage.sync.set({ pasteSafe: enabled });
  }
  await sendToActive({ type: "setPasteSafe", enabled: enabled });
});

(async function boot() {
  if (!hasChromeTabs()) {
    scanPage.disabled = true;
    revealPage.disabled = true;
    hidePage.disabled = true;
  }
  if (typeof chrome !== "undefined" && chrome.storage) {
    const stored = await chrome.storage.sync.get({ pasteSafe: false });
    pasteSafe.checked = Boolean(stored.pasteSafe);
    const session = chrome.storage.session
      ? await chrome.storage.session.get({ pendingSelection: "" })
      : { pendingSelection: "" };
    if (session.pendingSelection) {
      input.value = session.pendingSelection;
      await chrome.storage.session.set({ pendingSelection: "" });
    }
  }
  renderLocal();
})();
