import "./styles.css";
import { detectFuckMarkInsertions, transformText } from "./engine";
import { mountNav, renderCarriers, stat } from "./ui";

const SAMPLES = [
  { id: "ascii-eligible", title: "Eligible ASCII", source: "I do not agree." },
  { id: "ascii-apostrophe", title: "Straight ASCII apostrophe", source: "I don't agree." },
  { id: "curly-apostrophe", title: "Curly apostrophe (letters mixed)", source: "I don’t agree." },
  { id: "accented", title: "Accented Latin letter is a site", source: "I do not agree é." },
  { id: "han-only", title: "Han syllables", source: "中文" },
  { id: "emoji-only", title: "Emoji-only input", source: "😀" },
  { id: "path-url", title: "Path and URL stay intact", source: "Read src/main.py at https://example.com/a now." },
];

function stripMn(text: string): string {
  return text.replace(/\p{Mn}/gu, "");
}

function stripDI(text: string): string {
  return text.replace(/\p{Default_Ignorable_Code_Point}/gu, "");
}

function renderStatus(sample: ReturnType<typeof transformText>, extras?: { restored?: boolean }): void {
  const box = document.getElementById("status-grid")!;
  box.replaceChildren(
    stat("processed", sample.change_count > 0 ? "yes" : "no", sample.change_count > 0 ? "ok" : "warn"),
    stat("reason", sample.reason, sample.change_count > 0 ? "ok" : "warn"),
    stat("insertions", String(sample.change_count)),
    stat("sites", String(sample.site_count)),
    stat("last_index", sample.last_source_index == null ? "" : String(sample.last_source_index)),
    stat("source_length", String(sample.source_length)),
    stat("capped", sample.capped ? "yes" : "no", sample.capped ? "warn" : ""),
    stat("first_unsupported", sample.first_unsupported),
  );
  if (extras && extras.restored != null) {
    box.append(stat("strip restores source", extras.restored ? "yes" : "no", extras.restored ? "bad" : "ok"));
  }
}

function main(): void {
  mountNav("demo");
  const tabs = document.getElementById("sample-tabs")!;
  const view = document.getElementById("char-view")!;
  const note = document.getElementById("reversal-note")!;
  let activeSource = SAMPLES[0].source;
  let mode: "output" | "source" | "mn" | "di" = "output";

  function render(): void {
    const sample = transformText(activeSource);
    let text = sample.output_text;
    let extras: { restored?: boolean } | undefined;
    if (mode === "source") text = activeSource;
    if (mode === "mn") {
      text = stripMn(sample.output_text);
      extras = { restored: text === activeSource };
    }
    if (mode === "di") {
      text = stripDI(sample.output_text);
      extras = { restored: text === activeSource };
    }
    renderStatus(sample, extras);
    view.innerHTML = renderCarriers(text);
    if (mode === "mn" || mode === "di") {
      note.textContent = extras?.restored
        ? "Strip restored the exact source. That should not happen on live five-layer output."
        : "Strip did not restore the source. Me/Cc/Cf residuals remain after Mn or default-ignorable removal.";
    } else {
      note.textContent =
        "Use the strip buttons on a transformed sample. Five-layer residuals should keep the source from coming back.";
    }
  }

  SAMPLES.forEach((sample, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = sample.title;
    button.setAttribute("aria-selected", index === 0 ? "true" : "false");
    button.addEventListener("click", () => {
      activeSource = sample.source;
      mode = "output";
      for (const child of tabs.children) child.setAttribute("aria-selected", child === button ? "true" : "false");
      render();
    });
    tabs.appendChild(button);
  });

  document.getElementById("btn-show-output")?.addEventListener("click", () => {
    mode = "output";
    render();
  });
  document.getElementById("btn-show-source")?.addEventListener("click", () => {
    mode = "source";
    render();
  });
  document.getElementById("btn-strip-mn")?.addEventListener("click", () => {
    mode = "mn";
    render();
  });
  document.getElementById("btn-strip-di")?.addEventListener("click", () => {
    mode = "di";
    render();
  });

  document.getElementById("btn-detect")?.addEventListener("click", () => {
    const text = (document.getElementById("detect-input") as HTMLTextAreaElement).value;
    const resultBox = document.getElementById("detect-result")!;
    const statusBox = document.getElementById("detect-status")!;
    const detectView = document.getElementById("detect-view")!;
    statusBox.replaceChildren();
    if (!text) {
      resultBox.innerHTML =
        '<div class="panel"><p class="fail-title">Paste text first</p><p class="note">The detector checks this box only. It does not query a network service.</p></div>';
      return;
    }
    const scan = detectFuckMarkInsertions(text);
    if (scan.detected) {
      resultBox.innerHTML =
        '<div class="panel"><p class="fail-title">Detected FuckMark insertions</p><p class="note">Closed-set scan only. Not a general AI-watermark detector.</p></div>';
      statusBox.append(
        stat("local scan", "detected", "ok"),
        stat("found", String(scan.found), "ok"),
        stat("mark", String(scan.mark)),
        stat("cc", String(scan.cc)),
        stat("me", String(scan.me)),
        stat("cf", String(scan.cf)),
        stat("ia", String(scan.ia)),
        stat("first", scan.first),
      );
    } else {
      resultBox.innerHTML =
        '<div class="panel"><p class="fail-title">We did not detect a watermark in this text.</p><p class="note">What? You think there is a watermark in this? <a href="mailto:Fhelp@q1z.org">Contact us</a></p></div>';
      statusBox.append(stat("local scan", "not detected", "warn"), stat("found", "0"), stat("contact", "Fhelp@q1z.org"));
    }
    detectView.innerHTML = renderCarriers(text);
  });

  document.getElementById("btn-live")?.addEventListener("click", () => {
    const text = (document.getElementById("live-input") as HTMLTextAreaElement).value;
    const liveStatus = document.getElementById("live-status")!;
    const liveView = document.getElementById("live-view")!;
    const result = transformText(text);
    liveStatus.replaceChildren(
      stat("reason", result.reason, result.change_count > 0 ? "ok" : "warn"),
      stat("insertions", String(result.change_count)),
      stat("sites", String(result.site_count)),
      stat("first_unsupported", result.first_unsupported),
      stat("source_length", String(result.source_length)),
    );
    liveView.innerHTML = renderCarriers(result.output_text);
  });

  render();
}

main();
