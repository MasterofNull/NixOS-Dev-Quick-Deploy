//! `boundaries` check: token-level scan of Python and shell files for the five
//! cross-context call kinds (import, subprocess, HTTP, event, dynamic) against
//! the registry. KISS by design (DESIGN, "Rust contract guard"): a lexer, no AST
//! and no flow analysis. Declared limits: a computed target is flagged as
//! dynamic, never proven safe; an unparseable in-scope file fails closed.

use crate::registry::{path_matches, Context, Exception, Registry};
use crate::sha256::hex_digest;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, PartialEq)]
enum Kind {
    Name(String),
    Str { value: String, fstring: bool },
    Op(char),
    Comment(String),
    Newline,
    Num,
}

#[derive(Debug, Clone)]
struct Tok {
    kind: Kind,
    line: usize,
    start: bool,
}

#[derive(Debug, Clone)]
pub struct Raw {
    pub line: usize,
    pub kind: &'static str,
    pub detail: String,
    /// Context that owns the target (or the file's own context for dynamic calls).
    pub owner: String,
    /// What the caller must name instead (contract package, schema or id).
    pub contract: String,
    pub annotation: Option<String>,
}

#[derive(Default)]
pub struct Report {
    pub failures: Vec<String>,
    pub warnings: Vec<String>,
    pub scanned: usize,
    pub baselined: usize,
    /// Violations that remain after annotations (before exceptions), for `--emit-baseline`.
    pub open: BTreeMap<(String, String), (usize, String)>,
}

pub fn is_python(path: &str, first_line: &str) -> bool {
    path.ends_with(".py") || (first_line.starts_with("#!") && first_line.contains("python"))
}

pub fn is_shell(path: &str, first_line: &str) -> bool {
    path.ends_with(".sh")
        || path.ends_with(".bash")
        || (first_line.starts_with("#!")
            && (first_line.contains("bash")
                || first_line.contains("/sh")
                || first_line.contains("env sh")))
}

pub fn in_scope(reg: &Registry, path: &str) -> bool {
    reg.scan_scope.include.iter().any(|p| path_matches(path, p))
        && !reg
            .scan_scope
            .exclude
            .iter()
            .any(|p| path.contains(p.as_str()))
}

pub fn context_of<'a>(reg: &'a Registry, path: &str) -> Option<&'a Context> {
    reg.contexts
        .iter()
        .flat_map(|c| c.paths.iter().map(move |p| (c, p)))
        .filter(|(_, p)| path_matches(path, p))
        .max_by_key(|(_, p)| p.len())
        .map(|(c, _)| c)
}

fn lex_py(src: &str) -> Result<Vec<Tok>, String> {
    let chars: Vec<char> = src.chars().collect();
    let mut toks: Vec<Tok> = Vec::new();
    let (mut i, mut line, mut depth, mut at_start) = (0usize, 1usize, 0i32, true);
    while i < chars.len() {
        let c = chars[i];
        match c {
            '\n' => {
                if depth == 0 {
                    toks.push(Tok {
                        kind: Kind::Newline,
                        line,
                        start: false,
                    });
                    at_start = true;
                }
                line += 1;
                i += 1;
            }
            '\\' if matches!(chars.get(i + 1), Some('\n')) => {
                line += 1;
                i += 2;
            }
            '#' => {
                let begin = i + 1;
                while i < chars.len() && chars[i] != '\n' {
                    i += 1;
                }
                let text: String = chars[begin..i].iter().collect();
                toks.push(Tok {
                    kind: Kind::Comment(text),
                    line,
                    start: false,
                });
            }
            c if c.is_whitespace() => i += 1,
            c if c.is_alphabetic() || c == '_' => {
                let begin = i;
                while i < chars.len() && (chars[i].is_alphanumeric() || chars[i] == '_') {
                    i += 1;
                }
                let word: String = chars[begin..i].iter().collect();
                let is_prefix = word.len() <= 2 && word.chars().all(|p| "rbfuRBFU".contains(p));
                if is_prefix && matches!(chars.get(i), Some('"') | Some('\'')) {
                    let fstring = word.contains(['f', 'F']);
                    let (value, next, lines) = lex_string(&chars, i, line)?;
                    toks.push(Tok {
                        kind: Kind::Str { value, fstring },
                        line,
                        start: at_start,
                    });
                    line += lines;
                    i = next;
                } else {
                    toks.push(Tok {
                        kind: Kind::Name(word),
                        line,
                        start: at_start,
                    });
                }
                at_start = false;
            }
            '"' | '\'' => {
                let (value, next, lines) = lex_string(&chars, i, line)?;
                toks.push(Tok {
                    kind: Kind::Str {
                        value,
                        fstring: false,
                    },
                    line,
                    start: at_start,
                });
                line += lines;
                i = next;
                at_start = false;
            }
            c if c.is_ascii_digit() => {
                while i < chars.len()
                    && (chars[i].is_alphanumeric() || chars[i] == '.' || chars[i] == '_')
                {
                    i += 1;
                }
                toks.push(Tok {
                    kind: Kind::Num,
                    line,
                    start: at_start,
                });
                at_start = false;
            }
            _ => {
                match c {
                    '(' | '[' | '{' => depth += 1,
                    ')' | ']' | '}' => depth = (depth - 1).max(0),
                    _ => {}
                }
                toks.push(Tok {
                    kind: Kind::Op(c),
                    line,
                    start: at_start,
                });
                at_start = (c == ';') || (c == ':' && depth == 0);
                i += 1;
            }
        }
    }
    Ok(toks)
}

/// Returns (value, index after the closing quote, newlines consumed).
fn lex_string(chars: &[char], open: usize, line: usize) -> Result<(String, usize, usize), String> {
    let q = chars[open];
    let triple = chars.get(open + 1) == Some(&q) && chars.get(open + 2) == Some(&q);
    let mut i = open + if triple { 3 } else { 1 };
    let begin = i;
    let mut lines = 0;
    while i < chars.len() {
        let c = chars[i];
        if c == '\\' {
            if chars.get(i + 1) == Some(&'\n') {
                lines += 1;
            }
            i += 2;
            continue;
        }
        if c == '\n' {
            if !triple {
                return Ok((chars[begin..i].iter().collect(), i, lines));
            }
            lines += 1;
        }
        if c == q && (!triple || (chars.get(i + 1) == Some(&q) && chars.get(i + 2) == Some(&q))) {
            let value = chars[begin..i].iter().collect();
            return Ok((value, i + if triple { 3 } else { 1 }, lines));
        }
        i += 1;
    }
    if triple {
        Err(format!(
            "unterminated triple-quoted string opened at line {line}"
        ))
    } else {
        Ok((chars[begin..].iter().collect(), chars.len(), lines))
    }
}

fn module_matches(module: &str, pattern: &str) -> bool {
    module == pattern
        || module.starts_with(&format!("{pattern}."))
        || module.ends_with(&format!(".{pattern}"))
        || module.contains(&format!(".{pattern}."))
}

type Annotations = BTreeMap<usize, String>;

fn annotation_map(toks: &[Tok]) -> Annotations {
    let mut map = Annotations::new();
    for t in toks {
        if let Kind::Comment(text) = &t.kind {
            if let Some(rest) = text.trim().strip_prefix("contract:") {
                let id = rest.split_whitespace().next().unwrap_or("").to_string();
                map.insert(t.line, id);
            }
        }
    }
    map
}

fn annotation_for(anns: &Annotations, line: usize) -> Option<String> {
    anns.get(&line)
        .or_else(|| anns.get(&line.wrapping_sub(1)))
        .cloned()
}

struct FileCtx<'a> {
    reg: &'a Registry,
    own: String,
    own_allowed: Vec<String>,
}

fn args_end(toks: &[Tok], open: usize) -> usize {
    let mut depth = 0i32;
    for (j, t) in toks.iter().enumerate().skip(open) {
        if let Kind::Op(c) = t.kind {
            match c {
                '(' | '[' | '{' => depth += 1,
                ')' | ']' | '}' => {
                    depth -= 1;
                    if depth == 0 {
                        return j;
                    }
                }
                _ => {}
            }
        }
    }
    toks.len() - 1
}

fn name_at(toks: &[Tok], i: usize) -> Option<&str> {
    match toks.get(i).map(|t| &t.kind) {
        Some(Kind::Name(n)) => Some(n.as_str()),
        _ => None,
    }
}

fn op_at(toks: &[Tok], i: usize, c: char) -> bool {
    matches!(toks.get(i).map(|t| &t.kind), Some(Kind::Op(o)) if *o == c)
}

fn basename_word(value: &str) -> &str {
    let first = value.split_whitespace().next().unwrap_or("");
    first.rsplit('/').next().unwrap_or("")
}

fn scan_python(fc: &FileCtx<'_>, src: &str) -> Result<Vec<Raw>, String> {
    let toks = lex_py(src)?;
    let anns = annotation_map(&toks);
    let mut out = Vec::new();
    let reg = fc.reg;
    for i in 0..toks.len() {
        let line = toks[i].line;
        let ann = || annotation_for(&anns, line);
        match &toks[i].kind {
            Kind::Name(n) if toks[i].start && (n == "import" || n == "from") => {
                let mut candidates: Vec<String> = Vec::new();
                let mut j = i + 1;
                if n == "import" {
                    loop {
                        let mut dotted = String::new();
                        while let Some(part) = name_at(&toks, j) {
                            dotted.push_str(part);
                            j += 1;
                            if op_at(&toks, j, '.') {
                                dotted.push('.');
                                j += 1;
                            } else {
                                break;
                            }
                        }
                        if !dotted.is_empty() {
                            candidates.push(dotted);
                        }
                        if name_at(&toks, j) == Some("as") {
                            j += 2;
                        }
                        if op_at(&toks, j, ',') {
                            j += 1;
                        } else {
                            break;
                        }
                    }
                } else {
                    let mut relative = false;
                    while op_at(&toks, j, '.') {
                        relative = true;
                        j += 1;
                    }
                    let mut base = String::new();
                    while let Some(part) = name_at(&toks, j) {
                        if part == "import" {
                            break;
                        }
                        base.push_str(part);
                        j += 1;
                        if op_at(&toks, j, '.') {
                            base.push('.');
                            j += 1;
                        } else {
                            break;
                        }
                    }
                    if !relative && !base.is_empty() {
                        candidates.push(base.clone());
                        if name_at(&toks, j) == Some("import") {
                            j += 1;
                            while let Some(tok) = toks.get(j) {
                                match &tok.kind {
                                    Kind::Name(part) if part != "as" => {
                                        candidates.push(format!("{base}.{part}"));
                                    }
                                    Kind::Newline => break,
                                    Kind::Op(';') => break,
                                    _ => {}
                                }
                                j += 1;
                            }
                        }
                    }
                }
                let mut seen = BTreeSet::new();
                for module in candidates {
                    let Some(owner) = reg
                        .contexts
                        .iter()
                        .find(|c| c.modules.iter().any(|m| module_matches(&module, m)))
                    else {
                        continue;
                    };
                    if owner.id == fc.own
                        || fc.own_allowed.iter().any(|a| module_matches(&module, a))
                    {
                        continue;
                    }
                    if !seen.insert(owner.id.clone()) {
                        continue;
                    }
                    out.push(Raw {
                        line,
                        kind: "import",
                        detail: format!("import '{module}' crosses {} -> {}", fc.own, owner.id),
                        owner: owner.id.clone(),
                        contract: owner.contract_package.clone(),
                        annotation: ann(),
                    });
                }
            }
            Kind::Name(n) => {
                let prev_dot = i > 0 && op_at(&toks, i - 1, '.');
                let call = op_at(&toks, i + 1, '(');
                let dynamic = |what: &str| Raw {
                    line,
                    kind: "dynamic",
                    detail: format!("dynamic construct {what}"),
                    owner: fc.own.clone(),
                    contract: "annotate with `# contract: <id>` naming the enforcing contract"
                        .into(),
                    annotation: ann(),
                };
                match n.as_str() {
                    "__import__" | "import_module" | "spec_from_file_location" if call => {
                        out.push(dynamic(&format!("{n}()")));
                    }
                    "eval" | "exec" if call && !prev_dot => out.push(dynamic(&format!("{n}()"))),
                    "getattr" if call && !prev_dot => {
                        let end = args_end(&toks, i + 1);
                        let mut depth = 0i32;
                        let mut comma = None;
                        for (j, t) in toks.iter().enumerate().take(end).skip(i + 1) {
                            match t.kind {
                                Kind::Op('(' | '[' | '{') => depth += 1,
                                Kind::Op(')' | ']' | '}') => depth -= 1,
                                Kind::Op(',') if depth == 1 => {
                                    comma = Some(j);
                                    break;
                                }
                                _ => {}
                            }
                        }
                        if let Some(c) = comma {
                            let literal = matches!(
                                toks.get(c + 1).map(|t| &t.kind),
                                Some(Kind::Str { fstring: false, .. })
                            ) && matches!(
                                toks.get(c + 2).map(|t| &t.kind),
                                Some(Kind::Op(',' | ')'))
                            );
                            if !literal {
                                out.push(dynamic("getattr() with a computed attribute"));
                            }
                        }
                    }
                    "subprocess" | "os" if op_at(&toks, i + 1, '.') && !prev_dot => {
                        let Some(func) = name_at(&toks, i + 2) else {
                            continue;
                        };
                        let spawns = if n == "subprocess" {
                            matches!(
                                func,
                                "run"
                                    | "Popen"
                                    | "call"
                                    | "check_output"
                                    | "check_call"
                                    | "getoutput"
                                    | "getstatusoutput"
                            )
                        } else {
                            func == "system"
                                || func == "popen"
                                || func.starts_with("exec")
                                || func.starts_with("spawn")
                        };
                        if spawns && op_at(&toks, i + 3, '(') {
                            subprocess_hits(fc, &toks, &anns, i + 3, &mut out);
                        }
                    }
                    "Popen" | "check_output" | "check_call" if call && !prev_dot => {
                        subprocess_hits(fc, &toks, &anns, i + 1, &mut out);
                    }
                    "Envelope"
                        if call && !prev_dot && i > 0 && name_at(&toks, i - 1) != Some("class") =>
                    {
                        let end = args_end(&toks, i + 1);
                        for j in i + 2..end {
                            if name_at(&toks, j) == Some("type") && op_at(&toks, j + 1, '=') {
                                if let Some(Kind::Str { value, .. }) =
                                    toks.get(j + 2).map(|t| &t.kind)
                                {
                                    event_hit(fc, value, line, ann(), &mut out);
                                }
                            }
                        }
                    }
                    _ => {}
                }
            }
            Kind::Str { value, .. } if !toks[i].start => {
                http_hits(fc, value, line, ann(), &mut out)
            }
            _ => {}
        }
    }
    Ok(out)
}

fn subprocess_hits(
    fc: &FileCtx<'_>,
    toks: &[Tok],
    anns: &Annotations,
    open: usize,
    out: &mut Vec<Raw>,
) {
    let end = args_end(toks, open);
    for t in &toks[open..=end] {
        let Kind::Str { value, .. } = &t.kind else {
            continue;
        };
        tool_hit(
            fc,
            basename_word(value),
            t.line,
            annotation_for(anns, t.line),
            out,
        );
    }
}

fn tool_hit(
    fc: &FileCtx<'_>,
    word: &str,
    line: usize,
    annotation: Option<String>,
    out: &mut Vec<Raw>,
) {
    let Some(tool) = fc.reg.tools.iter().find(|t| t.id == word) else {
        return;
    };
    if tool.owner == fc.own || tool.callers.contains(&fc.own) {
        return;
    }
    let schema = fc
        .reg
        .decisions
        .iter()
        .find(|d| d.id == tool.decision)
        .map(|d| d.contract.clone())
        .filter(|c| !c.is_empty())
        .unwrap_or_else(|| format!("no CLI schema yet; decision {}", tool.decision));
    out.push(Raw {
        line,
        kind: "subprocess",
        detail: format!(
            "invokes {} (owned by {}) from {}",
            tool.id, tool.owner, fc.own
        ),
        owner: tool.owner.clone(),
        contract: schema,
        annotation,
    });
}

fn http_hits(
    fc: &FileCtx<'_>,
    text: &str,
    line: usize,
    annotation: Option<String>,
    out: &mut Vec<Raw>,
) {
    for ep in &fc.reg.endpoints {
        let by_env = ep
            .env_vars
            .iter()
            .any(|v| text == v || contains_word(text, v));
        let by_literal = ep.literals.iter().any(|l| text.contains(l.as_str()));
        if !(by_env || by_literal) || ep.owner == fc.own || ep.callers.contains(&fc.own) {
            continue;
        }
        out.push(Raw {
            line,
            kind: "http",
            detail: format!(
                "calls endpoint {} (owned by {}) from {}",
                ep.id, ep.owner, fc.own
            ),
            owner: ep.owner.clone(),
            contract: ep.contract.clone(),
            annotation: annotation.clone(),
        });
    }
}

fn contains_word(text: &str, word: &str) -> bool {
    text.match_indices(word).any(|(at, _)| {
        let before = text[..at].chars().next_back();
        let after = text[at + word.len()..].chars().next();
        !before.is_some_and(|c| c.is_alphanumeric() || c == '_')
            && !after.is_some_and(|c| c.is_alphanumeric() || c == '_')
    })
}

fn event_hit(
    fc: &FileCtx<'_>,
    event: &str,
    line: usize,
    annotation: Option<String>,
    out: &mut Vec<Raw>,
) {
    let declared = fc
        .reg
        .decisions
        .iter()
        .find(|d| d.events.iter().any(|e| e == event));
    let (owner, contract, bad) = match declared {
        Some(d) => (
            d.context.clone(),
            format!("event owned by {} ({})", d.id, d.context),
            d.context != fc.own,
        ),
        None => (
            "-".to_string(),
            "declare the event type in a decision row's events[]".to_string(),
            true,
        ),
    };
    if bad {
        out.push(Raw {
            line,
            kind: "event",
            detail: format!(
                "event type '{event}' emitted from {} without a matching declaration",
                fc.own
            ),
            owner,
            contract,
            annotation,
        });
    }
}

fn scan_shell(fc: &FileCtx<'_>, src: &str) -> Vec<Raw> {
    let mut out = Vec::new();
    let mut prev_comment: Option<(usize, String)> = None;
    for (idx, raw_line) in src.lines().enumerate() {
        let line = idx + 1;
        let (code, comment) = split_shell_comment(raw_line);
        let own_ann = comment
            .as_deref()
            .and_then(|c| c.trim().strip_prefix("contract:"))
            .map(|c| c.split_whitespace().next().unwrap_or("").to_string());
        let annotation = own_ann.clone().or_else(|| {
            prev_comment
                .as_ref()
                .filter(|(l, _)| *l + 1 == line)
                .map(|(_, a)| a.clone())
        });
        prev_comment = own_ann.map(|a| (line, a));
        if code.trim().is_empty() {
            continue;
        }
        http_hits(fc, &code, line, annotation.clone(), &mut out);
        for segment in code.split(['|', ';', '&', '(', '`']) {
            let words: Vec<&str> = segment.split_whitespace().collect();
            let mut k = 0;
            while k < words.len()
                && ((words[k].contains('=') && !words[k].starts_with('-'))
                    || matches!(
                        words[k],
                        "sudo"
                            | "exec"
                            | "command"
                            | "env"
                            | "time"
                            | "nohup"
                            | "then"
                            | "do"
                            | "$"
                            | "!"
                    ))
            {
                k += 1;
            }
            let Some(first) = words.get(k) else { continue };
            let word = first.trim_matches(['"', '\'']);
            let dynamic = |out: &mut Vec<Raw>, what: String| {
                out.push(Raw {
                    line,
                    kind: "dynamic",
                    detail: format!("dynamic construct {what}"),
                    owner: fc.own.clone(),
                    contract: "annotate with `# contract: <id>` naming the enforcing contract"
                        .into(),
                    annotation: annotation.clone(),
                })
            };
            match word {
                "eval" => dynamic(&mut out, "eval".into()),
                "sh" | "bash"
                    if words.get(k + 1) == Some(&"-c")
                        && words[k + 2..].iter().any(|w| w.contains('$')) =>
                {
                    dynamic(&mut out, format!("{word} -c with a computed command"));
                }
                "source" | "." => {
                    if let Some(arg) = words.get(k + 1) {
                        let arg = arg.trim_matches(['"', '\'']);
                        if arg.starts_with('$') && !arg.contains('/') {
                            dynamic(&mut out, format!("{word} of computed path {arg}"));
                        } else {
                            tool_hit(
                                fc,
                                arg.rsplit('/').next().unwrap_or(""),
                                line,
                                annotation.clone(),
                                &mut out,
                            );
                        }
                    }
                }
                _ => tool_hit(
                    fc,
                    word.rsplit('/').next().unwrap_or(""),
                    line,
                    annotation.clone(),
                    &mut out,
                ),
            }
        }
    }
    out
}

fn split_shell_comment(line: &str) -> (String, Option<String>) {
    let mut quote: Option<char> = None;
    let mut prev = ' ';
    for (at, c) in line.char_indices() {
        match quote {
            Some(q) => {
                if c == q {
                    quote = None;
                }
            }
            None => {
                if (c == '"' || c == '\'') && prev != '\\' {
                    quote = Some(c);
                } else if c == '#' && (prev.is_whitespace() || at == 0) {
                    return (line[..at].to_string(), Some(line[at + 1..].to_string()));
                }
            }
        }
        prev = c;
    }
    (line.to_string(), None)
}

/// Scan one file; `Ok(None)` means the file type is not scanned.
pub fn scan_file(reg: &Registry, path: &str, bytes: &[u8]) -> Result<Option<Vec<Raw>>, String> {
    let head = &bytes[..bytes.len().min(200)];
    let first_bytes = head.split(|b| *b == b'\n').next().unwrap_or(&[]);
    let first = String::from_utf8_lossy(first_bytes);
    let scannable = is_python(path, &first) || is_shell(path, &first);
    if !scannable {
        return Ok(None);
    }
    let text = std::str::from_utf8(bytes).map_err(|_| "file is not valid UTF-8".to_string())?;
    let ctx = context_of(reg, path);
    let fc = FileCtx {
        reg,
        own: ctx
            .map(|c| c.id.clone())
            .unwrap_or_else(|| "UNASSIGNED".to_string()),
        own_allowed: ctx.map(|c| c.allowed_imports.clone()).unwrap_or_default(),
    };
    if is_python(path, &first) {
        scan_python(&fc, text).map(Some)
    } else {
        Ok(Some(scan_shell(&fc, text)))
    }
}

fn known_ids(reg: &Registry) -> BTreeSet<String> {
    let mut ids: BTreeSet<String> = reg.decisions.iter().map(|d| d.id.clone()).collect();
    ids.extend(reg.endpoints.iter().map(|e| e.id.clone()));
    ids.extend(reg.tools.iter().map(|t| t.id.clone()));
    ids
}

/// Evaluate files (path, bytes) against the registry and its exceptions.
pub fn evaluate(
    reg: &Registry,
    files: &[(String, Vec<u8>)],
    today: &str,
    maintenance: bool,
    check_stale: bool,
) -> Report {
    let mut report = Report::default();
    let ids = known_ids(reg);
    let exceptions: BTreeMap<(String, String), &Exception> = reg
        .exceptions
        .iter()
        .map(|e| ((e.path.clone(), e.kind.clone()), e))
        .collect();
    let mut used: BTreeSet<(String, String)> = BTreeSet::new();
    let mut scanned_paths: BTreeSet<String> = BTreeSet::new();
    for (path, bytes) in files {
        if !in_scope(reg, path) {
            continue;
        }
        let raws = match scan_file(reg, path, bytes) {
            Ok(Some(raws)) => raws,
            Ok(None) => continue,
            Err(e) => {
                report.failures.push(format!(
                    "boundaries: {path}: unscannable ({e}); declared scope not scanned"
                ));
                continue;
            }
        };
        report.scanned += 1;
        scanned_paths.insert(path.clone());
        let mut open: BTreeMap<&'static str, Vec<Raw>> = BTreeMap::new();
        for raw in raws {
            match &raw.annotation {
                Some(id) if ids.contains(id) => continue,
                Some(id) => {
                    report.failures.push(format!(
                        "boundaries: {path}:{}: {}; annotation names unknown contract id '{id}'; owner: {} ({})",
                        raw.line, raw.detail, raw.owner, raw.contract
                    ));
                    continue;
                }
                None => open.entry(raw.kind).or_default().push(raw),
            }
        }
        let sha = hex_digest(bytes);
        for (kind, items) in open {
            let key = (path.clone(), kind.to_string());
            let owner = items[0].owner.clone();
            report
                .open
                .insert(key.clone(), (items.len(), format!("{owner}:{sha}")));
            let allowed = exceptions.get(&key).map(|e| e.count).unwrap_or(0);
            if exceptions.contains_key(&key) {
                used.insert(key);
            }
            if items.len() <= allowed {
                report.baselined += items.len();
                continue;
            }
            for raw in &items {
                report.failures.push(format!(
                    "boundaries: {path}:{}: {}: {}; owner: {} (must name: {}){}",
                    raw.line,
                    raw.kind,
                    raw.detail,
                    raw.owner,
                    raw.contract,
                    if allowed > 0 {
                        format!("; baseline allows {allowed}, found {}", items.len())
                    } else {
                        String::new()
                    }
                ));
            }
        }
    }
    for e in &reg.exceptions {
        let key = (e.path.clone(), e.kind.clone());
        let covered = scanned_paths.contains(&e.path);
        if check_stale && covered && !used.contains(&key) {
            report.warnings.push(format!(
                "boundaries: stale exception {}:{} (no longer needed; remove it)",
                e.path, e.kind
            ));
        }
        if e.expiry.as_str() < today && covered {
            let msg = format!(
                "boundaries: exception {}:{} expired on {}",
                e.path, e.kind, e.expiry
            );
            if maintenance {
                report.failures.push(msg);
            } else {
                report.warnings.push(msg);
            }
        }
    }
    report
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::registry::parse;

    const YAML: &str = "contexts:\n  - {id: K1, paths: [scripts/ai/lib/task_registry.py, ai-stack/mcp-servers/hybrid-coordinator/], modules: [task_registry], contract_package: contracts/k1}\n  - {id: K3, paths: [scripts/ai/aq-land], allowed_imports: []}\n  - {id: K2, paths: [ai-stack/switchboard/], allowed_imports: [event_log]}\ndecisions:\n  - {id: D05, decision: land, context: K3, owner: aq-land, tag: OV, events: [trace.span.start]}\n  - {id: D20, decision: deleg, context: K1, owner: coordinator, tag: OV}\ntools:\n  - {id: aq-land, path: scripts/ai/aq-land, owner: K3, decision: D05, callers: []}\nendpoints:\n  - {id: coordinator, owner: K1, contract: config/schemas/x.json, env_vars: [HYBRID_URL], literals: [\"127.0.0.1:8003\"], callers: []}\nscan_scope:\n  include: [scripts/, ai-stack/]\n  exclude: [scripts/testing/]\n";

    fn reg() -> Registry {
        parse(YAML).unwrap()
    }

    fn scan(path: &str, src: &str) -> Vec<Raw> {
        scan_file(&reg(), path, src.as_bytes()).unwrap().unwrap()
    }

    fn kinds(raws: &[Raw]) -> Vec<&'static str> {
        raws.iter().map(|r| r.kind).collect()
    }

    #[test]
    fn n5_import_violation_names_owner_and_contract_package() {
        let raws = scan(
            "scripts/ai/aq-land",
            "#!/usr/bin/env python3\nfrom lib.task_registry import TaskRegistry\n",
        );
        assert_eq!(kinds(&raws), vec!["import"]);
        assert_eq!(raws[0].owner, "K1");
        assert_eq!(raws[0].contract, "contracts/k1");
        assert!(scan(
            "scripts/ai/aq-land",
            "#!/usr/bin/env python3\nimport os\nfrom pathlib import Path\n"
        )
        .is_empty());
        assert!(scan(
            "ai-stack/mcp-servers/hybrid-coordinator/x.py",
            "import task_registry\n"
        )
        .is_empty());
    }

    #[test]
    fn n5_subprocess_http_event_and_dynamic_violations() {
        let raws = scan(
            "ai-stack/switchboard/a.py",
            "import subprocess\nsubprocess.run([\"aq-land\", \"--x\"])\n",
        );
        assert_eq!(kinds(&raws), vec!["subprocess"]);
        assert_eq!(raws[0].owner, "K3");
        let raws = scan(
            "ai-stack/switchboard/a.py",
            "import os\nurl = os.environ.get(\"HYBRID_URL\")\nu2 = \"http://127.0.0.1:8003/x\"\n",
        );
        assert_eq!(kinds(&raws), vec!["http", "http"]);
        assert_eq!(raws[0].owner, "K1");
        let raws = scan("ai-stack/switchboard/a.py", "e = Envelope(agent=\"a\", type=\"trace.span.start\")\nf = Envelope(agent=\"a\", type=\"nope.x\")\n");
        assert_eq!(kinds(&raws), vec!["event", "event"]);
        let raws = scan("ai-stack/switchboard/a.py", "import importlib\nm = importlib.import_module(name)\nx = getattr(obj, name)\neval(s)\nok = getattr(obj, \"a\", None)\n");
        assert_eq!(kinds(&raws), vec!["dynamic", "dynamic", "dynamic"]);
    }

    #[test]
    fn shell_calls_and_dynamic() {
        let raws = scan("scripts/ai/delegate-x.sh", "#!/usr/bin/env bash\nset -e\naq-land --check # fine\neval \"$CMD\"\nbash -c \"$X\"\ncurl \"$HYBRID_URL/x\"\n# aq-land in a comment\n");
        assert_eq!(
            kinds(&raws),
            vec!["subprocess", "dynamic", "dynamic", "http"]
        );
        let ann = scan(
            "scripts/ai/delegate-x.sh",
            "#!/usr/bin/env bash\n# contract: D05\naq-land --check\n",
        );
        assert_eq!(ann[0].annotation.as_deref(), Some("D05"));
    }

    #[test]
    fn strings_comments_and_docstrings_do_not_trigger() {
        let src = "\"\"\"uses HYBRID_URL and aq-land eval(x)\"\"\"\n# eval(x) HYBRID_URL\nlabel = 'eval( is text'\n";
        assert!(scan("ai-stack/switchboard/a.py", src).is_empty());
    }

    #[test]
    fn annotation_exception_and_ratchet_semantics() {
        let r = reg();
        let ok = (
            "scripts/ai/aq-land".to_string(),
            b"#!/usr/bin/env python3\n# contract: D20\nfrom lib.task_registry import T\n".to_vec(),
        );
        assert!(evaluate(&r, &[ok], "2026-11-27", false, true)
            .failures
            .is_empty());
        let bad_id = (
            "scripts/ai/aq-land".to_string(),
            b"#!/usr/bin/env python3\n# contract: D99\nfrom lib.task_registry import T\n".to_vec(),
        );
        assert!(
            evaluate(&r, &[bad_id], "2026-11-27", false, true).failures[0]
                .contains("unknown contract id")
        );
        let two = (
            "scripts/ai/aq-land".to_string(),
            b"#!/usr/bin/env python3\nimport task_registry\nfrom lib.task_registry import T\n"
                .to_vec(),
        );
        let mut with_exc = reg();
        with_exc.exceptions.push(Exception {
            path: "scripts/ai/aq-land".into(),
            kind: "import".into(),
            count: 2,
            owner: "K3".into(),
            reason: "r".into(),
            expiry: "2027-03-31".into(),
            source_sha256: "0".repeat(64),
        });
        let rep = evaluate(
            &with_exc,
            std::slice::from_ref(&two),
            "2026-11-27",
            false,
            true,
        );
        assert!(
            rep.failures.is_empty() && rep.baselined == 2,
            "{:?}",
            rep.failures
        );
        with_exc.exceptions[0].count = 1;
        let rep = evaluate(&with_exc, &[two], "2026-11-27", false, true);
        assert_eq!(rep.failures.len(), 2);
        assert!(rep.failures[0].contains("owner: K1"));
    }

    #[test]
    fn unparseable_in_scope_file_fails_closed() {
        let r = reg();
        let bad = (
            "scripts/ai/aq-land".to_string(),
            b"#!/usr/bin/env python3\nx = \"\"\"never closed\n".to_vec(),
        );
        assert!(evaluate(&r, &[bad], "2026-11-27", false, true).failures[0].contains("unscannable"));
        let binary = ("scripts/ai/x.py".to_string(), vec![0xff, 0xfe]);
        assert!(!evaluate(&r, &[binary], "2026-11-27", false, true)
            .failures
            .is_empty());
    }

    #[test]
    fn scope_excludes_tests_and_unlisted_trees() {
        let r = reg();
        assert!(in_scope(&r, "scripts/ai/x.py"));
        assert!(!in_scope(&r, "scripts/testing/test-x.py"));
        assert!(!in_scope(&r, "docs/x.py"));
    }
}
