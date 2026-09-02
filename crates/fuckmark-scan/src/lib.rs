pub const SCAN_ALGORITHM_VERSION: &str = "fuckmark-hidden-scan-v1";

pub const CATEGORY_BIDI_CONTROL: &str = "bidi_control";
pub const CATEGORY_ZERO_WIDTH: &str = "zero_width";
pub const CATEGORY_VARIATION_SELECTOR: &str = "variation_selector";
pub const CATEGORY_TAG: &str = "tag";
pub const CATEGORY_ENCLOSING_MARK: &str = "enclosing_mark";
pub const CATEGORY_LINE_SEPARATOR: &str = "line_separator";
pub const CATEGORY_DEPRECATED: &str = "deprecated";
pub const CATEGORY_FORMAT: &str = "format";
pub const CATEGORY_CONTROL: &str = "control";
pub const CATEGORY_PRIVATE_USE: &str = "private_use";
pub const CATEGORY_NONCHARACTER: &str = "noncharacter";
pub const CATEGORY_SURROGATE: &str = "surrogate";

pub const SCAN_CATEGORIES: [&str; 12] = [
    CATEGORY_BIDI_CONTROL,
    CATEGORY_ZERO_WIDTH,
    CATEGORY_VARIATION_SELECTOR,
    CATEGORY_TAG,
    CATEGORY_ENCLOSING_MARK,
    CATEGORY_LINE_SEPARATOR,
    CATEGORY_DEPRECATED,
    CATEGORY_FORMAT,
    CATEGORY_CONTROL,
    CATEGORY_PRIVATE_USE,
    CATEGORY_NONCHARACTER,
    CATEGORY_SURROGATE,
];

const ALLOWED_WHITESPACE: [u32; 4] = [0x09, 0x0A, 0x0D, 0x20];
const BIDI_EXTRA: [u32; 3] = [0x061C, 0x200E, 0x200F];
const ZERO_WIDTH: [u32; 18] = [
    0x00AD, 0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x180E, 0x200B, 0x200C, 0x200D, 0x2060, 0x2061,
    0x2062, 0x2063, 0x2064, 0x3164, 0xFEFF, 0xFFA0,
];
const FORMAT_RANGES: [(u32, u32); 10] = [
    (0x0600, 0x0605),
    (0x06DD, 0x06DD),
    (0x070F, 0x070F),
    (0x0890, 0x0891),
    (0x08E2, 0x08E2),
    (0x110BD, 0x110BD),
    (0x110CD, 0x110CD),
    (0x13430, 0x1343F),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
];
const EMOJI_BMP: [u32; 10] = [
    0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D, 0x3297, 0x3299,
];
const ZWJ: u32 = 0x200D;

fn in_range(cp: u32, lo: u32, hi: u32) -> bool {
    cp >= lo && cp <= hi
}

fn contains_u32(table: &[u32], cp: u32) -> bool {
    table.iter().any(|item| *item == cp)
}

pub fn classify(cp: u32) -> Option<&'static str> {
    if contains_u32(&ALLOWED_WHITESPACE, cp) {
        return None;
    }
    if contains_u32(&BIDI_EXTRA, cp) || in_range(cp, 0x202A, 0x202E) || in_range(cp, 0x2066, 0x2069)
    {
        return Some(CATEGORY_BIDI_CONTROL);
    }
    if in_range(cp, 0x206A, 0x206F) || cp == 0xFFF9 || cp == 0xFFFA || cp == 0xFFFB {
        return Some(CATEGORY_DEPRECATED);
    }
    if contains_u32(&ZERO_WIDTH, cp) {
        return Some(CATEGORY_ZERO_WIDTH);
    }
    if in_range(cp, 0xFE00, 0xFE0F) || in_range(cp, 0xE0100, 0xE01EF) {
        return Some(CATEGORY_VARIATION_SELECTOR);
    }
    if in_range(cp, 0xE0000, 0xE007F) {
        return Some(CATEGORY_TAG);
    }
    if in_range(cp, 0xFDD0, 0xFDEF) || (cp & 0xFFFF) == 0xFFFE || (cp & 0xFFFF) == 0xFFFF {
        return Some(CATEGORY_NONCHARACTER);
    }
    if in_range(cp, 0xD800, 0xDFFF) {
        return Some(CATEGORY_SURROGATE);
    }
    if in_range(cp, 0x0488, 0x0489)
        || cp == 0x1ABE
        || in_range(cp, 0x20DD, 0x20E0)
        || in_range(cp, 0x20E2, 0x20E4)
        || in_range(cp, 0xA670, 0xA672)
    {
        return Some(CATEGORY_ENCLOSING_MARK);
    }
    if cp == 0x2028 || cp == 0x2029 {
        return Some(CATEGORY_LINE_SEPARATOR);
    }
    if in_range(cp, 0x00, 0x1F) || in_range(cp, 0x7F, 0x9F) {
        return Some(CATEGORY_CONTROL);
    }
    if FORMAT_RANGES.iter().any(|(lo, hi)| in_range(cp, *lo, *hi)) {
        return Some(CATEGORY_FORMAT);
    }
    if in_range(cp, 0xE000, 0xF8FF)
        || in_range(cp, 0xF0000, 0xFFFFD)
        || in_range(cp, 0x100000, 0x10FFFD)
    {
        return Some(CATEGORY_PRIVATE_USE);
    }
    None
}

pub fn category_index(name: &str) -> Option<i32> {
    SCAN_CATEGORIES
        .iter()
        .position(|item| *item == name)
        .map(|index| index as i32)
}

pub fn classify_index(cp: u32) -> i32 {
    match classify(cp) {
        Some(name) => category_index(name).unwrap_or(-1),
        None => -1,
    }
}

pub fn normalize_language(language: &str) -> &'static str {
    let key = language.trim().to_ascii_lowercase();
    match key.as_str() {
        "" | "auto" => "auto",
        "javascript" | "js" | "ts" | "typescript" | "jsx" | "tsx" => "javascript",
        "c" | "h" | "cc" | "cpp" | "cxx" | "java" | "go" | "rs" | "rust" | "cs" | "css"
        | "jsonc" => "c",
        "python" | "py" | "pyi" | "hash" | "sh" | "bash" | "zsh" | "shell" | "shellscript"
        | "yaml" | "yml" | "rb" | "ruby" | "toml" => "python",
        "html" | "htm" | "xml" => "html",
        "sql" => "sql",
        _ => "auto",
    }
}

fn slash_comments(language: &str) -> bool {
    matches!(language, "auto" | "javascript" | "c" | "sql")
}

fn block_comments(language: &str) -> bool {
    slash_comments(language)
}

fn hash_comments(language: &str) -> bool {
    language == "python"
}

fn sql_line_comments(language: &str) -> bool {
    language == "sql"
}

fn html_comments(language: &str) -> bool {
    language == "html"
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Role {
    Code,
    String,
    Comment,
}

fn role_name(role: Role) -> &'static str {
    match role {
        Role::Code => "code",
        Role::String => "string",
        Role::Comment => "comment",
    }
}

fn find_seq(chars: &[char], start: usize, needle: &[char]) -> Option<usize> {
    if needle.is_empty() || start > chars.len() {
        return None;
    }
    chars[start..]
        .windows(needle.len())
        .position(|window| window == needle)
        .map(|offset| start + offset)
}

pub fn source_roles(text: &str, language: &str) -> Vec<&'static str> {
    let lang = normalize_language(language);
    let chars: Vec<char> = text.chars().collect();
    let mut roles = vec![Role::Code; chars.len()];
    let length = chars.len();
    let mut index = 0;
    let mut in_string: Option<char> = None;
    let mut escape = false;
    while index < length {
        let character = chars[index];
        if in_string.is_some() {
            roles[index] = Role::String;
            if escape {
                escape = false;
                index += 1;
                continue;
            }
            if character == '\\' && index + 1 < length {
                escape = true;
                index += 1;
                continue;
            }
            if Some(character) == in_string {
                in_string = None;
            }
            index += 1;
            continue;
        }
        let pair = if index + 1 < length {
            Some((character, chars[index + 1]))
        } else {
            None
        };
        if slash_comments(lang)
            && pair == Some(('/', '/'))
            && !(index > 0 && chars[index - 1] == ':')
        {
            let mut cursor = index;
            while cursor < length && chars[cursor] != '\n' && chars[cursor] != '\r' {
                roles[cursor] = Role::Comment;
                cursor += 1;
            }
            index = cursor;
            continue;
        }
        if sql_line_comments(lang) && pair == Some(('-', '-')) {
            let mut cursor = index;
            while cursor < length && chars[cursor] != '\n' && chars[cursor] != '\r' {
                roles[cursor] = Role::Comment;
                cursor += 1;
            }
            index = cursor;
            continue;
        }
        if block_comments(lang) && pair == Some(('/', '*')) {
            let close = find_seq(&chars, index + 2, &['*', '/']);
            let stop = close.map(|pos| pos + 2).unwrap_or(length);
            for role in roles.iter_mut().take(stop).skip(index) {
                *role = Role::Comment;
            }
            index = stop;
            continue;
        }
        if hash_comments(lang) && character == '#' {
            let mut cursor = index;
            while cursor < length && chars[cursor] != '\n' && chars[cursor] != '\r' {
                roles[cursor] = Role::Comment;
                cursor += 1;
            }
            index = cursor;
            continue;
        }
        if html_comments(lang) && chars.get(index..index + 4) == Some(&['<', '!', '-', '-'][..]) {
            let close = find_seq(&chars, index + 4, &['-', '-', '>']);
            let stop = close.map(|pos| pos + 3).unwrap_or(length);
            for role in roles.iter_mut().take(stop).skip(index) {
                *role = Role::Comment;
            }
            index = stop;
            continue;
        }
        if character == '"' || character == '\'' || character == '`' {
            in_string = Some(character);
            roles[index] = Role::String;
            index += 1;
            continue;
        }
        index += 1;
    }
    roles.into_iter().map(role_name).collect()
}

fn is_emojiish(cp: i32) -> bool {
    if cp < 0 {
        return false;
    }
    let cp = cp as u32;
    if in_range(cp, 0x1F1E6, 0x1F1FF)
        || in_range(cp, 0x1F000, 0x1FAFF)
        || in_range(cp, 0x2600, 0x27BF)
    {
        return true;
    }
    cp == ZWJ || contains_u32(&EMOJI_BMP, cp)
}

fn is_ident_char(ch: Option<char>) -> bool {
    match ch {
        Some('_') => true,
        Some(character) => character.is_alphanumeric(),
        None => false,
    }
}

fn is_bmp_vs(cp: i32) -> bool {
    cp >= 0 && in_range(cp as u32, 0xFE00, 0xFE0F)
}

pub fn classify_context(text: &str, index: usize, role: &str, category: &str) -> &'static str {
    let chars: Vec<char> = text.chars().collect();
    classify_context_chars(&chars, index, role, category)
}

fn classify_context_chars(
    chars: &[char],
    index: usize,
    role: &str,
    category: &str,
) -> &'static str {
    if index >= chars.len() {
        return "prose";
    }
    let prev = if index > 0 {
        Some(chars[index - 1])
    } else {
        None
    };
    let next = chars.get(index + 1).copied();
    let prev_cp = prev.map(|ch| ch as u32 as i32).unwrap_or(-1);
    let next_cp = next.map(|ch| ch as u32 as i32).unwrap_or(-1);
    if (role == "comment" || role == "string") && category == CATEGORY_BIDI_CONTROL {
        return if role == "comment" {
            "comment"
        } else {
            "string"
        };
    }
    if is_emojiish(prev_cp) || is_emojiish(next_cp) || is_bmp_vs(prev_cp) || is_bmp_vs(next_cp) {
        return "emoji";
    }
    if role == "comment" {
        return "comment";
    }
    if role == "string" {
        return "string";
    }
    if is_ident_char(prev) || is_ident_char(next) {
        return "identifier";
    }
    "prose"
}

pub fn score_severity(category: &str, context: &str) -> &'static str {
    if category == CATEGORY_TAG {
        return "critical";
    }
    if category == CATEGORY_BIDI_CONTROL {
        if matches!(context, "identifier" | "comment" | "string") {
            return "critical";
        }
        return "high";
    }
    if category == CATEGORY_ZERO_WIDTH {
        if context == "emoji" {
            return "info";
        }
        if context == "identifier" {
            return "high";
        }
        return "medium";
    }
    if category == CATEGORY_VARIATION_SELECTOR {
        return if context == "emoji" { "info" } else { "medium" };
    }
    if matches!(category, "control" | "noncharacter" | "surrogate") {
        return "high";
    }
    "medium"
}

pub fn explain_finding(
    category: &str,
    context: &str,
    severity: &str,
) -> (&'static str, &'static str) {
    if category == CATEGORY_BIDI_CONTROL && context == "identifier" {
        return (
            "Bidirectional override sits inside an identifier, so the glyphs can read differently than the bytes (Trojan Source).",
            "Strip the bidi control and keep the identifier left-to-right.",
        );
    }
    if category == CATEGORY_BIDI_CONTROL && context == "comment" {
        return (
            "Bidirectional override sits inside a comment, so commented-out code can appear to run (Trojan Source commenting-out).",
            "Strip the bidi control from the comment.",
        );
    }
    if category == CATEGORY_BIDI_CONTROL && context == "string" {
        return (
            "Bidirectional override sits inside a string, so the literal can appear to close early (Trojan Source stretched-string).",
            "Strip the bidi control from the string.",
        );
    }
    if category == CATEGORY_BIDI_CONTROL {
        return (
            "Bidirectional override can reorder nearby glyphs (Trojan Source class, CVE-2021-42574).",
            "Strip U+202A-U+202E / U+2066-U+2069 and rewrite the text left-to-right.",
        );
    }
    if category == CATEGORY_TAG {
        return (
            "Unicode tag characters encode a second ASCII string that models read and humans do not.",
            "Strip U+E0020-U+E007F; inspect tag_payload for the smuggled text.",
        );
    }
    if category == CATEGORY_ZERO_WIDTH && context == "emoji" {
        return (
            "Zero-width joiner or invisible mark inside an emoji cluster; usually a legitimate emoji sequence.",
            "Leave emoji ZWJ sequences unless you are sanitizing for a security boundary.",
        );
    }
    if category == CATEGORY_ZERO_WIDTH && context == "identifier" {
        return (
            "Zero-width character splits an identifier, breaking search and some compilers while looking unchanged.",
            "Strip the zero-width character from the identifier.",
        );
    }
    if category == CATEGORY_ZERO_WIDTH {
        return (
            "Invisible spacing or joining character that changes the byte stream without changing the glyphs.",
            "Strip the zero-width character.",
        );
    }
    if category == CATEGORY_VARIATION_SELECTOR && context == "emoji" {
        return (
            "Variation selector tunes an emoji glyph; usually benign.",
            "Keep emoji variation selectors unless you are stripping all hidden marks.",
        );
    }
    if severity == "high" {
        return (
            "Hidden or non-text codepoint that should not appear in ordinary source or prompts.",
            "Strip the character.",
        );
    }
    (
        "Hidden or format codepoint that is invisible or renderer-defined.",
        "Strip the character if this text crosses a trust boundary.",
    )
}

fn severity_rank(severity: &str) -> i32 {
    match severity {
        "info" => 0,
        "medium" => 1,
        "high" => 2,
        "critical" => 3,
        _ => -1,
    }
}

fn parse_categories(raw: &str) -> Option<Vec<&'static str>> {
    let trimmed = raw.trim();
    if trimmed == "*" {
        return None;
    }
    let mut selected = Vec::new();
    if trimmed.is_empty() {
        return Some(selected);
    }
    for part in trimmed.split(',') {
        let name = part.trim();
        if let Some(known) = SCAN_CATEGORIES.iter().copied().find(|item| *item == name) {
            if !selected.contains(&known) {
                selected.push(known);
            }
        }
    }
    Some(selected)
}

fn json_escape(s: &str) -> String {
    let mut out = String::from("\"");
    for character in s.chars() {
        match character {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

#[derive(Clone)]
pub struct HiddenFinding {
    pub index: usize,
    pub codepoint: u32,
    pub category: &'static str,
    pub context: &'static str,
    pub severity: &'static str,
    pub why: &'static str,
    pub remedy: &'static str,
}

pub struct ScanResult {
    pub source_length: usize,
    pub total: usize,
    pub truncated: bool,
    pub highest_severity: String,
    pub counts: Vec<(&'static str, usize)>,
    pub findings: Vec<HiddenFinding>,
}

pub fn scan_text(text: &str, language: &str, categories: &str, max_findings: i32) -> ScanResult {
    let selected = parse_categories(categories);
    let roles = source_roles(text, language);
    let chars: Vec<char> = text.chars().collect();
    let mut counts = [0usize; 12];
    let mut findings = Vec::new();
    let mut total = 0usize;
    let mut truncated = false;
    let mut peak = "";
    let cap = if max_findings < 0 {
        usize::MAX
    } else {
        max_findings as usize
    };
    for (index, character) in chars.iter().enumerate() {
        let code = *character as u32;
        let Some(category) = classify(code) else {
            continue;
        };
        if let Some(allowed) = selected.as_ref() {
            if !allowed.contains(&category) {
                continue;
            }
        }
        total += 1;
        if let Some(slot) = category_index(category) {
            counts[slot as usize] += 1;
        }
        let role = roles.get(index).copied().unwrap_or("code");
        let context = classify_context_chars(&chars, index, role, category);
        let severity = score_severity(category, context);
        let (why, remedy) = explain_finding(category, context, severity);
        if severity_rank(severity) > severity_rank(peak) {
            peak = severity;
        }
        if findings.len() < cap {
            findings.push(HiddenFinding {
                index,
                codepoint: code,
                category,
                context,
                severity,
                why,
                remedy,
            });
        } else {
            truncated = true;
        }
    }
    let mut named_counts = Vec::new();
    for (index, name) in SCAN_CATEGORIES.iter().enumerate() {
        if counts[index] > 0 {
            named_counts.push((*name, counts[index]));
        }
    }
    ScanResult {
        source_length: chars.len(),
        total,
        truncated,
        highest_severity: peak.to_string(),
        counts: named_counts,
        findings,
    }
}

pub fn clean_text(text: &str, categories: &str) -> (String, usize) {
    let selected = parse_categories(categories);
    let mut kept = String::new();
    let mut removed = 0usize;
    for character in text.chars() {
        let category = classify(character as u32);
        let drop = match (category, selected.as_ref()) {
            (Some(name), Some(allowed)) => allowed.contains(&name),
            (Some(_), None) => true,
            (None, _) => false,
        };
        if drop {
            removed += 1;
        } else {
            kept.push(character);
        }
    }
    (kept, removed)
}

pub fn scan_to_json(text: &str, language: &str, categories: &str, max_findings: i32) -> String {
    let result = scan_text(text, language, categories, max_findings);
    let mut out = String::from("{");
    out.push_str("\"algorithm_version\":");
    out.push_str(&json_escape(SCAN_ALGORITHM_VERSION));
    out.push_str(",\"source_length\":");
    out.push_str(&result.source_length.to_string());
    out.push_str(",\"total\":");
    out.push_str(&result.total.to_string());
    out.push_str(",\"truncated\":");
    out.push_str(if result.truncated { "true" } else { "false" });
    out.push_str(",\"highest_severity\":");
    out.push_str(&json_escape(&result.highest_severity));
    out.push_str(",\"counts\":{");
    for (index, (name, count)) in result.counts.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        out.push_str(&json_escape(name));
        out.push(':');
        out.push_str(&count.to_string());
    }
    out.push_str("},\"findings\":[");
    for (index, finding) in result.findings.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        out.push('{');
        out.push_str("\"index\":");
        out.push_str(&finding.index.to_string());
        out.push_str(",\"codepoint\":");
        out.push_str(&finding.codepoint.to_string());
        out.push_str(",\"category\":");
        out.push_str(&json_escape(finding.category));
        out.push_str(",\"context\":");
        out.push_str(&json_escape(finding.context));
        out.push_str(",\"severity\":");
        out.push_str(&json_escape(finding.severity));
        out.push_str(",\"why\":");
        out.push_str(&json_escape(finding.why));
        out.push_str(",\"remedy\":");
        out.push_str(&json_escape(finding.remedy));
        out.push('}');
    }
    out.push_str("]}");
    out
}

pub fn clean_to_json(text: &str, categories: &str) -> String {
    let (cleaned, removed) = clean_text(text, categories);
    let mut out = String::from("{\"removed\":");
    out.push_str(&removed.to_string());
    out.push_str(",\"cleaned\":");
    out.push_str(&json_escape(&cleaned));
    out.push('}');
    out
}

fn pack_bytes(payload: &[u8]) -> *mut u8 {
    let mut buffer = vec![0u8; 4 + payload.len()];
    buffer[..4].copy_from_slice(&(payload.len() as u32).to_le_bytes());
    buffer[4..].copy_from_slice(payload);
    let ptr = buffer.as_mut_ptr();
    std::mem::forget(buffer);
    ptr
}

fn read_bytes<'a>(ptr: *const u8, len: u32) -> &'a [u8] {
    if ptr.is_null() || len == 0 {
        return &[];
    }
    unsafe { std::slice::from_raw_parts(ptr, len as usize) }
}

#[no_mangle]
pub extern "C" fn fm_alloc(size: u32) -> *mut u8 {
    let mut buffer = vec![0u8; size as usize];
    let ptr = buffer.as_mut_ptr();
    std::mem::forget(buffer);
    ptr
}

#[no_mangle]
pub extern "C" fn fm_dealloc(ptr: *mut u8, size: u32) {
    if ptr.is_null() {
        return;
    }
    unsafe {
        let _ = Vec::from_raw_parts(ptr, size as usize, size as usize);
    }
}

#[no_mangle]
pub extern "C" fn fm_classify(cp: u32) -> i32 {
    classify_index(cp)
}

#[no_mangle]
pub extern "C" fn fm_scan(
    text_ptr: *const u8,
    text_len: u32,
    lang_ptr: *const u8,
    lang_len: u32,
    cats_ptr: *const u8,
    cats_len: u32,
    max_findings: i32,
) -> *mut u8 {
    let text = match std::str::from_utf8(read_bytes(text_ptr, text_len)) {
        Ok(value) => value.to_owned(),
        Err(_) => return pack_bytes(br#"{"ok":false,"reason":"utf8"}"#),
    };
    let language = std::str::from_utf8(read_bytes(lang_ptr, lang_len))
        .unwrap_or("auto")
        .to_owned();
    let categories = std::str::from_utf8(read_bytes(cats_ptr, cats_len))
        .unwrap_or("")
        .to_owned();
    let json = scan_to_json(&text, &language, &categories, max_findings);
    pack_bytes(json.as_bytes())
}

#[no_mangle]
pub extern "C" fn fm_clean(
    text_ptr: *const u8,
    text_len: u32,
    cats_ptr: *const u8,
    cats_len: u32,
) -> *mut u8 {
    let text = match std::str::from_utf8(read_bytes(text_ptr, text_len)) {
        Ok(value) => value.to_owned(),
        Err(_) => return pack_bytes(br#"{"ok":false,"reason":"utf8"}"#),
    };
    let categories = std::str::from_utf8(read_bytes(cats_ptr, cats_len))
        .unwrap_or("")
        .to_owned();
    let json = clean_to_json(&text, &categories);
    pack_bytes(json.as_bytes())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn classifies_core_hidden_codepoints() {
        assert_eq!(classify(0x202E), Some(CATEGORY_BIDI_CONTROL));
        assert_eq!(classify(0x200B), Some(CATEGORY_ZERO_WIDTH));
        assert_eq!(classify(0xE0061), Some(CATEGORY_TAG));
        assert_eq!(classify(0x20DD), Some(CATEGORY_ENCLOSING_MARK));
        assert_eq!(classify(0x13430), Some(CATEGORY_FORMAT));
        assert_eq!(classify(0x09), None);
        assert_eq!(classify(0x61), None);
        assert_eq!(classify(0x0301), None);
    }

    #[test]
    fn bidi_in_identifier_is_critical() {
        let text: String = ['a', '\u{202E}', 'b'].into_iter().collect();
        let result = scan_text(&text, "auto", "*", -1);
        assert_eq!(result.total, 1);
        assert_eq!(result.findings[0].context, "identifier");
        assert_eq!(result.findings[0].severity, "critical");
    }

    #[test]
    fn url_slash_slash_is_not_a_comment() {
        let text = "http://example.com/\u{202E}";
        let roles = source_roles(text, "auto");
        assert!(roles.iter().all(|role| *role == "code"));
        let result = scan_text(text, "auto", "*", -1);
        assert_eq!(result.findings[0].context, "prose");
        assert_eq!(result.findings[0].severity, "high");
    }

    #[test]
    fn python_hash_comment_is_critical_bidi() {
        let text = "x = 1  # \u{202E} no";
        let result = scan_text(text, "python", "*", -1);
        assert_eq!(result.findings[0].context, "comment");
        assert_eq!(result.findings[0].severity, "critical");
        let auto = scan_text(text, "auto", "*", -1);
        assert_ne!(auto.findings[0].context, "comment");
    }

    #[test]
    fn emoji_zwj_is_info() {
        let text = "\u{1F468}\u{200D}\u{1F469}";
        let result = scan_text(text, "auto", "*", -1);
        assert_eq!(result.findings[0].context, "emoji");
        assert_eq!(result.findings[0].severity, "info");
    }

    #[test]
    fn clean_strips_bidi_only() {
        let text = "a\u{202E}b\u{200B}c";
        let (cleaned, removed) = clean_text(text, "bidi_control");
        assert_eq!(removed, 1);
        assert_eq!(cleaned, "ab\u{200B}c");
    }

    #[test]
    fn empty_category_selection_finds_and_removes_nothing() {
        let text = "a\u{202E}b\u{200B}c";
        let empty = scan_text(text, "auto", "", -1);
        assert_eq!(empty.total, 0);
        assert!(empty.findings.is_empty());
        let all = scan_text(text, "auto", "*", -1);
        assert_eq!(all.total, 2);
        let (cleaned, removed) = clean_text(text, "");
        assert_eq!(removed, 0);
        assert_eq!(cleaned, text);
    }

    #[test]
    fn dense_zero_width_scan_stays_linear() {
        let text = "\u{200B}".repeat(20_000);
        let result = scan_text(&text, "auto", "*", -1);
        assert_eq!(result.total, 20_000);
        assert_eq!(result.findings.len(), 20_000);
    }
}
