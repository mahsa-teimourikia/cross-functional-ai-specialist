# Contributing a Course

Develop courses sequentially. Do not mark a roadmap title as ready until the complete learner
path is ready.

## Required artifacts

Each course owns one directory under `curriculum/advanced/<number>-<slug>/` with:

- `README.md`: chapter-level teaching and authoritative references;
- one primary `.ipynb`: credential-free guided lab;
- `lab.py`: reusable deterministic implementation;
- `checkpoint.json`: focused architecture/failure-analysis questions;
- topic-specific assets only when they materially improve learning.

Tests live under `tests/`; full-quiz questions live in `quiz/questions.json`; Hub metadata lives in
`hub/lessons.json`.

## Required teaching sequence

Motivation → mental model → foundations → internal mechanics → architecture alternatives → tooling
landscape → state of the art → worked scenario → implementation → experiments → evaluation →
failures → production upgrade → exercises → references.

## Publication gates

```bash
uv sync --locked
uv run ruff check .
uv run python scripts/typecheck_labs.py
uv run pytest
uv run python scripts/validate_repo.py
uv run jupyter execute <course-notebook> --inplace
```

After automation passes, reread claims against code. Typed output is not proof of authorization or
truth; mock quality is not live-model quality; blocked attacks are not the same as prevented
forbidden outcomes; and printed “success” is not verified completion.
