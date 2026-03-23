## Summary
<!-- One sentence: what does this PR do and why? -->

## Type of change
- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / tech debt
- [ ] Documentation
- [ ] CI / tooling

## Checklist
- [ ] `ruff format kpi_lens/` — no diff
- [ ] `ruff check kpi_lens/` — zero warnings
- [ ] `mypy kpi_lens/ --ignore-missing-imports` — zero errors
- [ ] `pytest tests/unit/ --cov=kpi_lens --cov-fail-under=80` — passes
- [ ] `pytest tests/integration/ --no-cov` — passes
- [ ] New public functions have full type annotations
- [ ] Architecture constraints respected (see `.claude/CLAUDE.md`)
- [ ] No secrets or real API keys in any tracked file

## Related issues
<!-- Closes #X -->
