# Default review criteria (every review)

1. Check correctness, tests, and security of the change.
2. Fails-without-the-fix: for a bug fix or a new gate/test, the change must show evidence that the new/changed test FAILS against the pre-fix code (command + output in the PR body or evidence doc). A test that cannot fail is a finding.
3. Claims cite measurements: any capability, limit, performance or enforcement claim in the diff or PR body (for example "cannot run X", "takes Y min", "is not enforced", "is the cause") must cite the probe, command or output that shows it. Uncited claims are findings.
