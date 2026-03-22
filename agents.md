# Agent Rules

- Replace magic numbers and repeated string literals with named constants when they are reused or carry behavior/significance.
- Always delete generated `.pyc` files and `__pycache__/` directories once they are no longer needed.
- Do not make stylistic-only changes unless the user explicitly asks for them.
- Never perform full-block or full-file rewrites for small changes.
- Use line-scoped edits only (apply_patch with minimal hunks, or exact single-line replacement).
- Before staging, verify diff is functional-only; do not include formatting/style churn unless explicitly requested.
- Reject any edit that changes more than 10 unrelated lines for a single-purpose fix; reapply with a narrower edit strategy.
