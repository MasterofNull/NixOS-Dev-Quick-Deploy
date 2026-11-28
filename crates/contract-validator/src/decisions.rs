//! `decisions --count`: overlap and orphan counts from the registry.
//!
//! Follow-up F1: the overlapping-ROW count and the excess-WRITER total are two
//! separate metrics. The writer total is `sum(max(0, writers - 1))` over rows and
//! is printed as unknown whenever a row that may overlap has no verified writer
//! list; a verified lower bound is printed beside it.

use crate::registry::Registry;

pub struct Counts {
    pub rows: usize,
    pub overlap_verified: Vec<String>,
    pub overlap_carried: Vec<String>,
    pub unverified: Vec<String>,
    pub orphans: Vec<String>,
    pub new_rows: Vec<String>,
    pub single_owner: Vec<String>,
    pub writer_lower_bound: usize,
    /// Rows whose excess-writer contribution cannot be computed.
    pub writer_unknown_rows: Vec<String>,
}

pub fn count(reg: &Registry) -> Counts {
    let mut c = Counts {
        rows: reg.decisions.len(),
        overlap_verified: Vec::new(),
        overlap_carried: Vec::new(),
        unverified: Vec::new(),
        orphans: Vec::new(),
        new_rows: Vec::new(),
        single_owner: Vec::new(),
        writer_lower_bound: 0,
        writer_unknown_rows: Vec::new(),
    };
    for d in &reg.decisions {
        let bucket = match d.tag.as_str() {
            "OV" => &mut c.overlap_verified,
            "OVc" => &mut c.overlap_carried,
            "UQ" => &mut c.unverified,
            "OR" => &mut c.orphans,
            "NEW" => &mut c.new_rows,
            _ => &mut c.single_owner,
        };
        bucket.push(d.id.clone());
        let may_overlap = matches!(d.tag.as_str(), "OV" | "OVc" | "UQ" | "NEW");
        if d.writers_verified {
            c.writer_lower_bound += d.writers.len().saturating_sub(1);
        } else if may_overlap {
            c.writer_unknown_rows.push(d.id.clone());
        }
    }
    c
}

pub fn render(c: &Counts) -> String {
    let list = |v: &[String]| {
        if v.is_empty() {
            "-".to_string()
        } else {
            v.join(" ")
        }
    };
    let writer_total = if c.writer_unknown_rows.is_empty() {
        c.writer_lower_bound.to_string()
    } else {
        format!(
            "unknown ({} rows lack a verified writer list)",
            c.writer_unknown_rows.len()
        )
    };
    format!(
        "decisions: {rows} rows\n\
         overlapping rows: verified {ov} [{ovl}]; carried {ovc} [{ovcl}]; unverified {uq} [{uql}]\n\
         excess-writer total: {writer_total}; verified lower bound {lb}\n\
         orphans: {orph} [{orphl}]; new {new} [{newl}]; single-owner {so} [{sol}]",
        rows = c.rows,
        ov = c.overlap_verified.len(),
        ovl = list(&c.overlap_verified),
        ovc = c.overlap_carried.len(),
        ovcl = list(&c.overlap_carried),
        uq = c.unverified.len(),
        uql = list(&c.unverified),
        lb = c.writer_lower_bound,
        orph = c.orphans.len(),
        orphl = list(&c.orphans),
        new = c.new_rows.len(),
        newl = list(&c.new_rows),
        so = c.single_owner.len(),
        sol = list(&c.single_owner),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::registry::parse;

    #[test]
    fn rows_and_writers_are_reported_separately_and_total_is_unknown() {
        let reg = parse("decisions:\n  - {id: D01, tag: OV, writers: [a, b, c], writers_verified: false}\n  - {id: D02, tag: OK, writers: [a], writers_verified: true}\n  - {id: D03, tag: OR}\n  - {id: D04, tag: OV, writers: [a, b], writers_verified: true}\n").unwrap();
        let c = count(&reg);
        assert_eq!(c.overlap_verified, vec!["D01", "D04"]);
        assert_eq!(c.writer_lower_bound, 1);
        assert_eq!(c.writer_unknown_rows, vec!["D01"]);
        let text = render(&c);
        assert!(text.contains("overlapping rows: verified 2"));
        assert!(text.contains("excess-writer total: unknown (1 rows"));
        assert!(text.contains("orphans: 1 [D03]"));
    }

    #[test]
    fn writer_total_is_numeric_when_all_rows_verified() {
        let reg = parse(
            "decisions:\n  - {id: D01, tag: OV, writers: [a, b, c], writers_verified: true}\n",
        )
        .unwrap();
        assert!(render(&count(&reg)).contains("excess-writer total: 2;"));
    }
}
