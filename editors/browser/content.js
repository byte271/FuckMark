"use strict";

const HIGHLIGHT_NAME = "fuckmark-hidden";
const HOST_ID = "fuckmark-overlay-host";
const MAX_BADGES = 256;

let pasteSafeEnabled = false;
let revealOn = false;
let overlay = null;
let highlightSet = null;

function pageApi() {
  return globalThis.FuckMarkPage;
}

function scanApi() {
  return pageApi().getScan();
}

function loadSettings() {
  if (typeof chrome === "undefined" || !chrome.storage) return;
  chrome.storage.sync.get({ pasteSafe: false }, (items) => {
    pasteSafeEnabled = Boolean(items && items.pasteSafe);
  });
}

function skipNode(node) {
  if (!node) return true;
  if (node.nodeType === Node.ELEMENT_NODE) {
    if (node.id === HOST_ID) return true;
    if (pageApi().isSkipTag(node.tagName)) return true;
  }
  const parent = node.parentElement;
  if (parent && pageApi().isSkipTag(parent.tagName)) return true;
  return false;
}

function walkTextNodes(root, visit) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue) return NodeFilter.FILTER_REJECT;
      if (skipNode(node) || skipNode(node.parentElement)) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  let node = walker.nextNode();
  while (node) {
    visit(node);
    node = walker.nextNode();
  }
}

function scanDocument() {
  let total = 0;
  let highest = "";
  const findings = [];
  const rank = { info: 1, medium: 2, high: 3, critical: 4 };
  walkTextNodes(document.body || document.documentElement, (node) => {
    const result = scanApi().scanText(node.nodeValue, null, "auto");
    total += result.total;
    for (const finding of result.findings) {
      if ((rank[finding.severity] || 0) > (rank[highest] || 0)) highest = finding.severity;
      if (findings.length < MAX_BADGES) {
        findings.push({ node, finding });
      }
    }
  });
  return { total, highest, findings };
}

function ensureOverlay() {
  if (overlay) return overlay;
  const host = document.createElement("div");
  host.id = HOST_ID;
  host.setAttribute("aria-hidden", "true");
  host.style.position = "absolute";
  host.style.left = "0";
  host.style.top = "0";
  host.style.width = "0";
  host.style.height = "0";
  host.style.zIndex = "2147483646";
  host.style.pointerEvents = "none";
  const shadow = host.attachShadow({ mode: "closed" });
  const style = document.createElement("style");
  style.textContent =
    ".badge{position:absolute;transform:translateY(-110%);font:11px/1.2 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;padding:2px 4px;border-radius:4px;white-space:nowrap;background:#1a1a1a;color:#ff5555;box-shadow:0 2px 8px rgba(0,0,0,.4);opacity:.95}" +
    ".badge.high{color:#ff9944}" +
    ".badge.medium{color:#c8a800}" +
    ".badge.info{color:#c8c8c4}";
  const layer = document.createElement("div");
  shadow.append(style, layer);
  (document.documentElement || document.body).appendChild(host);
  overlay = { host, layer };
  return overlay;
}

function clearReveal() {
  revealOn = false;
  if (highlightSet && typeof CSS !== "undefined" && CSS.highlights) {
    CSS.highlights.delete(HIGHLIGHT_NAME);
  }
  highlightSet = null;
  if (overlay && overlay.layer) overlay.layer.replaceChildren();
}

function fallbackRect(node, offset) {
  const range = document.createRange();
  const index = Math.max(0, offset - 1);
  try {
    range.setStart(node, index);
    range.setEnd(node, Math.min(node.nodeValue.length, index + 1));
    const rects = range.getClientRects();
    if (rects.length) return rects[0];
  } catch (_err) {
    return null;
  }
  const parent = node.parentElement;
  return parent ? parent.getBoundingClientRect() : null;
}

function paintReveal(entries) {
  const layer = ensureOverlay().layer;
  layer.replaceChildren();
  const scrollX = window.scrollX;
  const scrollY = window.scrollY;
  const canHighlight = typeof Highlight === "function" && typeof CSS !== "undefined" && CSS.highlights;
  const set = canHighlight ? new Highlight() : null;
  let painted = 0;
  for (const { node, finding } of entries) {
    if (painted >= MAX_BADGES) break;
    const start = finding.offset;
    const end = Math.min(node.nodeValue.length, start + (finding.length || 1));
    const range = document.createRange();
    try {
      range.setStart(node, start);
      range.setEnd(node, end);
    } catch (_err) {
      continue;
    }
    if (set) set.add(range);
    const rects = range.getClientRects();
    const rect = rects.length ? rects[0] : fallbackRect(node, start);
    if (!rect) continue;
    const badge = document.createElement("span");
    const severity = finding.severity || "medium";
    badge.className = "badge" + (severity === "critical" ? "" : " " + severity);
    badge.textContent = scanApi().codepointToken(finding.codepoint);
    badge.style.left = Math.round(rect.left + scrollX) + "px";
    badge.style.top = Math.round(rect.top + scrollY) + "px";
    layer.appendChild(badge);
    painted += 1;
  }
  if (set) {
    CSS.highlights.set(HIGHLIGHT_NAME, set);
    highlightSet = set;
    if (!document.getElementById("fuckmark-highlight-style")) {
      const style = document.createElement("style");
      style.id = "fuckmark-highlight-style";
      style.textContent = "::highlight(" + HIGHLIGHT_NAME + "){background-color:rgba(255,85,85,.38);}";
      document.documentElement.appendChild(style);
    }
  }
}

function revealPage() {
  const scanned = scanDocument();
  revealOn = true;
  paintReveal(scanned.findings);
  reportBadge(scanned.total);
  return scanned;
}

function hidePage() {
  clearReveal();
}

function reportBadge(total) {
  if (typeof chrome === "undefined" || !chrome.runtime) return;
  try {
    chrome.runtime.sendMessage({ type: "badge", total: total });
  } catch (_err) {
    return;
  }
}

function insertCleaned(target, cleaned) {
  if (!target) return false;
  if ((target.tagName === "TEXTAREA" || target.tagName === "INPUT") && target.type !== "password") {
    const start = target.selectionStart;
    const end = target.selectionEnd;
    if (typeof start === "number" && typeof target.setRangeText === "function") {
      target.setRangeText(cleaned, start, end, "end");
      target.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    }
  }
  if (target.isContentEditable && document.execCommand) {
    return document.execCommand("insertText", false, cleaned);
  }
  return false;
}

document.addEventListener(
  "paste",
  (event) => {
    if (!pasteSafeEnabled) return;
    const target = event.target;
    if (target && target.type === "password") return;
    const data = event.clipboardData;
    if (!data) return;
    const text = data.getData("text/plain");
    if (!text) return;
    const result = pageApi().cleanForPaste(text);
    if (result.removed === 0) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    insertCleaned(event.target, result.cleaned);
  },
  true
);

if (typeof chrome !== "undefined" && chrome.storage) {
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "sync" || !changes.pasteSafe) return;
    pasteSafeEnabled = Boolean(changes.pasteSafe.newValue);
  });
}

if (typeof chrome !== "undefined" && chrome.runtime) {
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || typeof message.type !== "string") return;
    if (message.type === "ping") {
      sendResponse({ ok: true });
      return;
    }
    if (message.type === "setPasteSafe") {
      pasteSafeEnabled = Boolean(message.enabled);
      sendResponse({ ok: true, pasteSafe: pasteSafeEnabled });
      return;
    }
    if (message.type === "scan") {
      const scanned = scanDocument();
      reportBadge(scanned.total);
      sendResponse({
        ok: true,
        total: scanned.total,
        highest: scanned.highest,
        shown: scanned.findings.length,
      });
      return;
    }
    if (message.type === "reveal") {
      const scanned = revealPage();
      sendResponse({
        ok: true,
        total: scanned.total,
        highest: scanned.highest,
        shown: scanned.findings.length,
      });
      return;
    }
    if (message.type === "hide") {
      hidePage();
      sendResponse({ ok: true });
      return;
    }
    if (message.type === "cleanSelection") {
      const text = String(message.text || window.getSelection());
      const result = pageApi().cleanForPaste(text);
      sendResponse({ ok: true, cleaned: result.cleaned, removed: result.removed });
      return;
    }
  });
}

loadSettings();
window.addEventListener("scroll", () => {
  if (!revealOn) return;
  paintReveal(scanDocument().findings);
}, { passive: true });
window.addEventListener("resize", () => {
  if (!revealOn) return;
  paintReveal(scanDocument().findings);
});
