//! Minimal YAML-subset reader for the contract sections of
//! `config/system-state-authorities.yaml` (the crate stays dependency-free).
//!
//! Supported: block maps, block sequences (scalar or map items), flow sequences
//! and flow maps on one line, quoted and plain scalars, `#` comments. Anything
//! else (anchors, block scalars, tags, multi-line flow) is an error so an
//! unparseable section fails closed instead of being silently skipped.

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Str(String),
    Seq(Vec<Value>),
    Map(Vec<(String, Value)>),
}

impl Value {
    pub fn get(&self, key: &str) -> Option<&Value> {
        match self {
            Value::Map(items) => items.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }

    pub fn str_of(&self, key: &str) -> String {
        match self.get(key) {
            Some(Value::Str(s)) => s.clone(),
            _ => String::new(),
        }
    }

    pub fn seq_of(&self, key: &str) -> Vec<Value> {
        match self.get(key) {
            Some(Value::Seq(items)) => items.clone(),
            _ => Vec::new(),
        }
    }

    pub fn strs_of(&self, key: &str) -> Vec<String> {
        self.seq_of(key)
            .into_iter()
            .filter_map(|v| match v {
                Value::Str(s) => Some(s),
                _ => None,
            })
            .collect()
    }
}

/// One top-level section: key, 1-based line of the key, parsed value.
pub struct Section {
    pub key: String,
    pub line: usize,
    pub value: Value,
}

struct Line {
    indent: usize,
    text: String,
    no: usize,
}

/// Parse only the top-level sections named in `wanted`; reject duplicate
/// top-level keys anywhere in the document.
pub fn parse_sections(text: &str, wanted: &[&str]) -> Result<Vec<Section>, String> {
    let mut seen: Vec<String> = Vec::new();
    let mut blocks: Vec<(String, usize, String, Vec<Line>)> = Vec::new();
    for (idx, raw) in text.lines().enumerate() {
        let no = idx + 1;
        let first = raw.chars().next();
        if matches!(first, Some(c) if c.is_ascii_alphabetic() || c == '_') {
            let Some(colon) = raw.find(':') else {
                return Err(format!("line {no}: top-level line without ':'"));
            };
            let key = raw[..colon].trim().to_string();
            if seen.contains(&key) {
                return Err(format!("line {no}: duplicate top-level key '{key}'"));
            }
            seen.push(key.clone());
            let rest = strip_comment(&raw[colon + 1..]).trim().to_string();
            blocks.push((key, no, rest, Vec::new()));
            continue;
        }
        let stripped = strip_comment(raw);
        if stripped.trim().is_empty() {
            continue;
        }
        if first == Some('\t') {
            return Err(format!("line {no}: tab indentation is not supported"));
        }
        if let Some(block) = blocks.last_mut() {
            let indent = stripped.len() - stripped.trim_start().len();
            block.3.push(Line {
                indent,
                text: stripped.trim().to_string(),
                no,
            });
        }
    }
    let mut out = Vec::new();
    for (key, no, rest, lines) in blocks {
        if !wanted.contains(&key.as_str()) {
            continue;
        }
        let value = if !rest.is_empty() {
            if !lines.is_empty() {
                return Err(format!(
                    "line {no}: '{key}' has an inline value and a block"
                ));
            }
            parse_inline(&rest, no)?
        } else if lines.is_empty() {
            Value::Seq(Vec::new())
        } else {
            let mut lines = lines;
            let base = lines[0].indent;
            let (value, next) = parse_block(&mut lines, 0, base)?;
            if next != lines.len() {
                return Err(format!("line {}: unexpected indentation", lines[next].no));
            }
            value
        };
        out.push(Section {
            key,
            line: no,
            value,
        });
    }
    Ok(out)
}

fn strip_comment(line: &str) -> String {
    let mut out = String::new();
    let mut quote: Option<char> = None;
    let mut prev_ws = true;
    let mut escaped = false;
    for c in line.chars() {
        match quote {
            Some(q) => {
                out.push(c);
                if escaped {
                    escaped = false;
                } else if c == '\\' && q == '"' {
                    escaped = true;
                } else if c == q {
                    quote = None;
                }
            }
            None => {
                if c == '#' && prev_ws {
                    break;
                }
                if (c == '"' || c == '\'') && prev_ws {
                    quote = Some(c);
                }
                out.push(c);
                prev_ws = c.is_whitespace() || c == '[' || c == '{' || c == ',' || c == ':';
            }
        }
    }
    out.trim_end().to_string()
}

fn parse_block(lines: &mut [Line], start: usize, indent: usize) -> Result<(Value, usize), String> {
    if lines[start].text == "-" || lines[start].text.starts_with("- ") {
        parse_seq(lines, start, indent)
    } else {
        parse_map(lines, start, indent)
    }
}

fn parse_seq(lines: &mut [Line], start: usize, indent: usize) -> Result<(Value, usize), String> {
    let mut items = Vec::new();
    let mut idx = start;
    while idx < lines.len() && lines[idx].indent == indent {
        if !(lines[idx].text == "-" || lines[idx].text.starts_with("- ")) {
            break;
        }
        let no = lines[idx].no;
        let rest = lines[idx].text[1..].trim().to_string();
        if rest.is_empty() {
            idx += 1;
            if idx >= lines.len() || lines[idx].indent <= indent {
                return Err(format!("line {no}: empty sequence item"));
            }
            let child = lines[idx].indent;
            let (value, next) = parse_block(lines, idx, child)?;
            items.push(value);
            idx = next;
        } else if is_map_entry(&rest) {
            let child = indent + 2;
            lines[idx].indent = child;
            lines[idx].text = rest;
            let (value, next) = parse_map(lines, idx, child)?;
            items.push(value);
            idx = next;
        } else {
            items.push(parse_inline(&rest, no)?);
            idx += 1;
        }
    }
    Ok((Value::Seq(items), idx))
}

fn parse_map(lines: &mut [Line], start: usize, indent: usize) -> Result<(Value, usize), String> {
    let mut items: Vec<(String, Value)> = Vec::new();
    let mut idx = start;
    while idx < lines.len() && lines[idx].indent == indent {
        let no = lines[idx].no;
        let text = lines[idx].text.clone();
        if text == "-" || text.starts_with("- ") {
            break;
        }
        let Some((key, rest)) = split_entry(&text) else {
            return Err(format!("line {no}: expected 'key: value', got '{text}'"));
        };
        if items.iter().any(|(k, _)| *k == key) {
            return Err(format!("line {no}: duplicate key '{key}'"));
        }
        idx += 1;
        let value = if rest.is_empty() {
            if idx < lines.len() && lines[idx].indent > indent {
                let child = lines[idx].indent;
                let (value, next) = parse_block(lines, idx, child)?;
                idx = next;
                value
            } else {
                Value::Str(String::new())
            }
        } else {
            parse_inline(&rest, no)?
        };
        items.push((key, value));
    }
    Ok((Value::Map(items), idx))
}

fn is_map_entry(text: &str) -> bool {
    !text.starts_with(['"', '\'', '[', '{']) && split_entry(text).is_some()
}

fn split_entry(text: &str) -> Option<(String, String)> {
    let bytes = text.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b':' && (i + 1 == bytes.len() || bytes[i + 1] == b' ') {
            let key = text[..i].trim();
            if key.is_empty() || key.contains(['"', '\'', '[', '{']) {
                return None;
            }
            return Some((key.to_string(), text[i + 1..].trim().to_string()));
        }
        i += 1;
    }
    None
}

fn parse_inline(text: &str, no: usize) -> Result<Value, String> {
    let text = text.trim();
    if text.starts_with('[') {
        let inner = text
            .strip_prefix('[')
            .and_then(|t| t.strip_suffix(']'))
            .ok_or_else(|| format!("line {no}: unterminated flow sequence"))?;
        let mut items = Vec::new();
        for part in split_flow(inner, no)? {
            items.push(parse_inline(&part, no)?);
        }
        return Ok(Value::Seq(items));
    }
    if text.starts_with('{') {
        let inner = text
            .strip_prefix('{')
            .and_then(|t| t.strip_suffix('}'))
            .ok_or_else(|| format!("line {no}: unterminated flow map"))?;
        let mut items: Vec<(String, Value)> = Vec::new();
        for part in split_flow(inner, no)? {
            let Some((key, rest)) = split_entry(&part) else {
                return Err(format!("line {no}: bad flow map entry '{part}'"));
            };
            if items.iter().any(|(k, _)| *k == key) {
                return Err(format!("line {no}: duplicate key '{key}'"));
            }
            items.push((key, parse_inline(&rest, no)?));
        }
        return Ok(Value::Map(items));
    }
    scalar(text, no)
}

fn split_flow(inner: &str, no: usize) -> Result<Vec<String>, String> {
    let mut parts = Vec::new();
    let mut cur = String::new();
    let mut depth = 0i32;
    let mut quote: Option<char> = None;
    let mut escaped = false;
    for c in inner.chars() {
        if let Some(q) = quote {
            cur.push(c);
            if escaped {
                escaped = false;
            } else if c == '\\' && q == '"' {
                escaped = true;
            } else if c == q {
                quote = None;
            }
            continue;
        }
        match c {
            '"' | '\'' => {
                quote = Some(c);
                cur.push(c);
            }
            '[' | '{' => {
                depth += 1;
                cur.push(c);
            }
            ']' | '}' => {
                depth -= 1;
                cur.push(c);
            }
            ',' if depth == 0 => {
                parts.push(cur.trim().to_string());
                cur.clear();
            }
            _ => cur.push(c),
        }
    }
    if quote.is_some() || depth != 0 {
        return Err(format!("line {no}: unbalanced flow collection"));
    }
    if !cur.trim().is_empty() {
        parts.push(cur.trim().to_string());
    }
    Ok(parts)
}

fn scalar(text: &str, no: usize) -> Result<Value, String> {
    if let Some(body) = text.strip_prefix('"') {
        let body = body
            .strip_suffix('"')
            .ok_or_else(|| format!("line {no}: unterminated double-quoted scalar"))?;
        let mut out = String::new();
        let mut chars = body.chars();
        while let Some(c) = chars.next() {
            if c == '\\' {
                match chars.next() {
                    Some('n') => out.push('\n'),
                    Some('t') => out.push('\t'),
                    Some(other) => out.push(other),
                    None => return Err(format!("line {no}: dangling escape")),
                }
            } else {
                out.push(c);
            }
        }
        return Ok(Value::Str(out));
    }
    if let Some(body) = text.strip_prefix('\'') {
        let body = body
            .strip_suffix('\'')
            .ok_or_else(|| format!("line {no}: unterminated single-quoted scalar"))?;
        return Ok(Value::Str(body.replace("''", "'")));
    }
    if text.starts_with(['&', '*', '!', '|', '>', '%', '@', '`']) {
        return Err(format!("line {no}: unsupported YAML construct '{text}'"));
    }
    if text == "null" || text == "~" {
        return Ok(Value::Str(String::new()));
    }
    Ok(Value::Str(text.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_nested_sections() {
        let doc = "meta:\n  x: 1\ndecisions:\n  - id: D01\n    readers: [a, \"b c\"]\n    ev: {k: v, n: 2}\n  - id: D02\n    contract: ''\n";
        let sections = parse_sections(doc, &["decisions"]).unwrap();
        let items = sections[0].value.seq_of("x");
        assert!(items.is_empty());
        let Value::Seq(rows) = &sections[0].value else {
            panic!("seq expected")
        };
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0].str_of("id"), "D01");
        assert_eq!(rows[0].strs_of("readers"), vec!["a", "b c"]);
        assert_eq!(rows[0].get("ev").unwrap().str_of("n"), "2");
        assert_eq!(rows[1].str_of("contract"), "");
    }

    #[test]
    fn rejects_duplicate_top_level_and_unsupported() {
        assert!(parse_sections("a: 1\na: 2\n", &["a"]).is_err());
        assert!(parse_sections("a:\n  - &x 1\n", &["a"]).is_err());
        assert!(parse_sections("a:\n  k: |\n    text\n", &["a"]).is_err());
    }

    #[test]
    fn comment_inside_quotes_is_kept() {
        let sections = parse_sections("a:\n  - \"x # y\" # real comment\n", &["a"]).unwrap();
        assert_eq!(
            sections[0].value,
            Value::Seq(vec![Value::Str("x # y".to_string())])
        );
    }
}
