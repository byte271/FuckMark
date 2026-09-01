# FuckMark guard — sanitize model input

`fuckmark.protect` and `fuckmark guard` sit in front of an LLM call and remove
hidden Unicode that a human reviewer cannot see but a model will still read.
The headline case is Unicode **tag** characters (U+E0020–U+E007E), which encode
a second ASCII string inside otherwise ordinary text — a prompt-injection
smuggling trick. Bidirectional overrides, zero-width characters, C0/C1
controls, noncharacters, and lone surrogates are stripped by default too.

This is **not** a semantic prompt-injection detector. It does not judge whether
visible text is trying to jailbreak a model. It only removes characters that
hide a second payload in the byte stream.

## One-liner

```python
from fuckmark import protect

safe = protect(user_text)
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": safe}],
)
```

`protect` walks strings, lists, and dicts, so this also works:

```python
payload = protect({
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": user_text}],
})
```

## Recover the smuggled text

Unicode tags are a cipher for ASCII. `extract_tag_payload` and the guard
receipt decode them so you can log what an attacker tried to hide:

```python
from fuckmark import extract_tag_payload, inspect

cleaned, receipt = inspect(user_text)
if receipt.tag_payload:
    log.warning("hidden tag payload: %r", receipt.tag_payload)
```

## Refuse instead of stripping

```python
from fuckmark import Guard, HiddenTextRefused

guard = Guard(on_findings="refuse")
try:
    safe = guard.protect(user_text)
except HiddenTextRefused as error:
    raise HttpError(400, "hidden characters in prompt") from error
```

`on_findings` is `strip` (default), `refuse`, or `report` (scan only).

## Wrap any complete function

```python
from fuckmark.guard import Guard

@Guard().wrap
def complete(messages):
    return client.chat.completions.create(model="gpt-4o-mini", messages=messages)
```

Every string argument is sanitized before the inner function runs. In `refuse`
mode the inner function is not called.

## Command line

```text
printf 'user text\n' | fuckmark guard
fuckmark guard --json < messages.json
fuckmark guard --refuse --receipt --json < messages.json
```

Plain text in, cleaned text out. `--json` walks every string in a JSON
document (OpenAI/Anthropic chat bodies included). `--refuse` exits `1` and
writes nothing if hidden Unicode is present. `--receipt` prints the JSON
receipt on stderr, including any recovered tag payload. Exit `0` means the
payload was written (clean or stripped); exit `1` is refuse; exit `2` is usage.

Default categories match `fuckmark lint` (the security set). `--select all`
includes variation selectors and format controls.

## HTTP

`fuckmark web` serves `POST /api/guard` with `{ "text": "..." }` or
`{ "messages": [...] }` and optional `"on_findings": "strip"|"refuse"|"report"`.

## JavaScript

`editors/vscode/guard.js` is the same protect / tag-decode path for Node,
pinned to the Python engine by `tests/test_guard.py`.
