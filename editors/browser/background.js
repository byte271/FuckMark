"use strict";

const MENU_SCAN = "fuckmark-scan-page";
const MENU_REVEAL = "fuckmark-reveal-page";
const MENU_HIDE = "fuckmark-hide-page";
const MENU_SCAN_SELECTION = "fuckmark-scan-selection";

function setBadge(total) {
  const text = total > 0 ? String(Math.min(total, 99)) : "";
  const color = total > 0 ? "#c62828" : "#666666";
  chrome.action.setBadgeBackgroundColor({ color: color });
  chrome.action.setBadgeText({ text: text });
}

function sendToTab(tabId, message) {
  return chrome.tabs.sendMessage(tabId, message).catch(() => null);
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: MENU_SCAN,
      title: "FuckMark: scan this page",
      contexts: ["page"],
    });
    chrome.contextMenus.create({
      id: MENU_REVEAL,
      title: "FuckMark: reveal hidden Unicode",
      contexts: ["page"],
    });
    chrome.contextMenus.create({
      id: MENU_HIDE,
      title: "FuckMark: hide reveal",
      contexts: ["page"],
    });
    chrome.contextMenus.create({
      id: MENU_SCAN_SELECTION,
      title: "FuckMark: scan selection",
      contexts: ["selection"],
    });
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!tab || tab.id == null) return;
  if (info.menuItemId === MENU_SCAN) {
    const result = await sendToTab(tab.id, { type: "scan" });
    if (result && result.ok) setBadge(result.total);
    return;
  }
  if (info.menuItemId === MENU_REVEAL) {
    const result = await sendToTab(tab.id, { type: "reveal" });
    if (result && result.ok) setBadge(result.total);
    return;
  }
  if (info.menuItemId === MENU_HIDE) {
    await sendToTab(tab.id, { type: "hide" });
    return;
  }
  if (info.menuItemId === MENU_SCAN_SELECTION) {
    await chrome.storage.session.set({ pendingSelection: String(info.selectionText || "") });
    chrome.action.openPopup().catch(() => {});
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message.type !== "string") return;
  if (message.type === "badge") {
    setBadge(Number(message.total) || 0);
    sendResponse({ ok: true });
  }
});
