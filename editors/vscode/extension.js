"use strict";

const vscode = require("vscode");
const {
  SCAN_ALGORITHM_VERSION,
  CATEGORY_DESCRIPTIONS,
  DEFAULT_SECURITY_CATEGORIES,
  codepointToken,
  scanText,
  cleanText,
} = require("./scan.js");

let decorationType;
let diagnostics;
let statusBar;
let revealEnabled = true;

function config() {
  return vscode.workspace.getConfiguration("fuckmark");
}

function securitySet() {
  return new Set(DEFAULT_SECURITY_CATEGORIES);
}

function maxBytes() {
  const value = config().get("maxFileSize", 5000000);
  return typeof value === "number" && value > 0 ? value : 5000000;
}

function shouldSkip(document) {
  if (document.uri.scheme === "output" || document.uri.scheme === "vscode") {
    return true;
  }
  return document.getText().length > maxBytes();
}

function categoryLabel(finding) {
  const token = codepointToken(finding.codepoint);
  const description = CATEGORY_DESCRIPTIONS[finding.category] || finding.category;
  return { token, description };
}

function buildDecorations(document, findings) {
  const security = securitySet();
  return findings.map((finding) => {
    const start = document.positionAt(finding.offset);
    const end = document.positionAt(finding.offset + finding.length);
    const { token, description } = categoryLabel(finding);
    const severe = security.has(finding.category);
    const md = new vscode.MarkdownString(
      "**FuckMark: " +
        (finding.severity || "hidden") +
        "**\n\n" +
        "`" +
        token +
        "` — " +
        (finding.why || description) +
        "\n\ncategory: `" +
        finding.category +
        "` · context: `" +
        (finding.context || "prose") +
        "`" +
        (severe ? "\n\n**High risk** (Trojan Source / smuggling class)." : "")
    );
    md.isTrusted = false;
    return {
      range: new vscode.Range(start, end),
      hoverMessage: md,
      renderOptions: {
        after: {
          contentText: "\u2039" + token + "\u203a",
          color: severe ? "#ff5555" : "#c8a800",
          fontWeight: "bold",
          margin: "0 0 0 1px",
        },
      },
    };
  });
}

function buildDiagnostics(document, findings) {
  const security = securitySet();
  return findings.map((finding) => {
    const start = document.positionAt(finding.offset);
    const end = document.positionAt(finding.offset + finding.length);
    const { token, description } = categoryLabel(finding);
    const rank = finding.severity || "";
    const vscodeSeverity =
      rank === "critical"
        ? vscode.DiagnosticSeverity.Error
        : rank === "high" || security.has(finding.category)
          ? vscode.DiagnosticSeverity.Warning
          : vscode.DiagnosticSeverity.Information;
    const diagnostic = new vscode.Diagnostic(
      new vscode.Range(start, end),
      (finding.why || description) + " [" + token + " " + finding.category + "]",
      vscodeSeverity
    );
    diagnostic.source = "FuckMark";
    diagnostic.code = SCAN_ALGORITHM_VERSION;
    return diagnostic;
  });
}

function refresh(editor) {
  if (!editor) {
    return { total: 0 };
  }
  const document = editor.document;
  if (shouldSkip(document)) {
    diagnostics.delete(document.uri);
    editor.setDecorations(decorationType, []);
    return { total: 0 };
  }
  const result = scanText(document.getText());
  diagnostics.set(document.uri, buildDiagnostics(document, result.findings));
  editor.setDecorations(decorationType, revealEnabled ? buildDecorations(document, result.findings) : []);
  return result;
}

function updateStatusBar(result) {
  if (!statusBar) {
    return;
  }
  const total = result ? result.total : 0;
  if (total > 0) {
    statusBar.text = "$(eye) Hidden: " + total;
    statusBar.tooltip = "FuckMark found " + total + " hidden characters. Click to clean.";
    statusBar.backgroundColor = new vscode.ThemeColor("statusBarItem.warningBackground");
    statusBar.show();
  } else {
    statusBar.text = "$(check) No hidden text";
    statusBar.tooltip = "FuckMark: no hidden characters in this file.";
    statusBar.backgroundColor = undefined;
    if (config().get("statusBar.alwaysShow", true)) {
      statusBar.show();
    } else {
      statusBar.hide();
    }
  }
}

function refreshActive() {
  const editor = vscode.window.activeTextEditor;
  updateStatusBar(refresh(editor));
}

async function replaceWholeDocument(editor, cleaned) {
  const document = editor.document;
  const fullRange = new vscode.Range(
    document.positionAt(0),
    document.positionAt(document.getText().length)
  );
  await editor.edit((builder) => builder.replace(fullRange, cleaned));
}

async function cleanDocumentCommand() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    return;
  }
  const original = editor.document.getText();
  const { cleaned, removed } = cleanText(original);
  if (removed === 0) {
    vscode.window.showInformationMessage("FuckMark: no hidden characters to remove.");
    return;
  }
  await replaceWholeDocument(editor, cleaned);
  vscode.window.showInformationMessage("FuckMark: removed " + removed + " hidden characters.");
  refreshActive();
}

async function cleanSelectionCommand() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.selection.isEmpty) {
    vscode.window.showInformationMessage("FuckMark: select some text first.");
    return;
  }
  const selectionText = editor.document.getText(editor.selection);
  const { cleaned, removed } = cleanText(selectionText);
  if (removed === 0) {
    vscode.window.showInformationMessage("FuckMark: no hidden characters in the selection.");
    return;
  }
  await editor.edit((builder) => builder.replace(editor.selection, cleaned));
  vscode.window.showInformationMessage("FuckMark: removed " + removed + " hidden characters from the selection.");
  refreshActive();
}

function toggleRevealCommand() {
  revealEnabled = !revealEnabled;
  vscode.window.showInformationMessage(
    "FuckMark reveal " + (revealEnabled ? "enabled" : "disabled") + "."
  );
  refreshActive();
}

function activate(context) {
  decorationType = vscode.window.createTextEditorDecorationType({
    backgroundColor: "rgba(255, 85, 85, 0.25)",
    border: "1px solid rgba(255, 85, 85, 0.8)",
    borderRadius: "2px",
    overviewRulerColor: "#ff5555",
    overviewRulerLane: vscode.OverviewRulerLane.Right,
  });
  diagnostics = vscode.languages.createDiagnosticCollection("fuckmark");
  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBar.command = "fuckmark.cleanDocument";

  context.subscriptions.push(
    decorationType,
    diagnostics,
    statusBar,
    vscode.commands.registerCommand("fuckmark.cleanDocument", cleanDocumentCommand),
    vscode.commands.registerCommand("fuckmark.cleanSelection", cleanSelectionCommand),
    vscode.commands.registerCommand("fuckmark.toggleReveal", toggleRevealCommand),
    vscode.commands.registerCommand("fuckmark.rescan", refreshActive),
    vscode.window.onDidChangeActiveTextEditor(refreshActive),
    vscode.workspace.onDidChangeTextDocument((event) => {
      const editor = vscode.window.activeTextEditor;
      if (editor && event.document === editor.document) {
        refreshActive();
      }
    }),
    vscode.workspace.onWillSaveTextDocument((event) => {
      if (!config().get("cleanOnSave", false)) {
        return;
      }
      if (shouldSkip(event.document)) {
        return;
      }
      const original = event.document.getText();
      const { cleaned, removed } = cleanText(original);
      if (!removed) {
        return;
      }
      const fullRange = new vscode.Range(
        event.document.positionAt(0),
        event.document.positionAt(original.length)
      );
      event.waitUntil(Promise.resolve([vscode.TextEdit.replace(fullRange, cleaned)]));
    }),
    vscode.workspace.onDidCloseTextDocument((document) => diagnostics.delete(document.uri))
  );

  refreshActive();
}

function deactivate() {
  if (diagnostics) {
    diagnostics.clear();
  }
}

module.exports = { activate, deactivate };
