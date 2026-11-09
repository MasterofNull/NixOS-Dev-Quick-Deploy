# Lesson tests: relative-time fixture recovery

2026-11-09: `agent_lesson_candidates` filters events before grouping. Test
fixtures must therefore derive fresh timestamps from one aware UTC `now` and
assert expired same-key events do not inflate candidate counts. Use
`tempfile.TemporaryDirectory` for patched aq-report feedback and registry paths,
then restore both globals in `finally`.
