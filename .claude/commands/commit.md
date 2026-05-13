<!--
Skill: commit
Role: implementer
Inputs: validation evidence, logical slice
Outputs: git commit and push
Example: /commit "fix(auth): resolve token expiration bug"
-->
---
description: Commit current isolated slice
---

# Commit Slice

1. Confirm one logical slice.
2. Confirm validation evidence exists.
3. Commit with atomic message (`feat|fix|docs|refactor`).
4. Push.
