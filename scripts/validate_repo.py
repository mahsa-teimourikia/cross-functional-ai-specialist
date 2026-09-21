"""Validate curriculum registry, assessments, notebooks, and local links."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_question_set(path: Path, questions: list[dict[str, Any]]) -> None:
    identifiers: set[str] = set()
    for question in questions:
        required = {"id", "category", "prompt", "options", "answer", "explanation"}
        missing = required - question.keys()
        assert not missing, f"{path}: missing {sorted(missing)}"
        assert question["id"] not in identifiers, f"{path}: duplicate {question['id']}"
        identifiers.add(question["id"])
        assert 2 <= len(question["options"]) <= 6, f"{path}: invalid options"
        assert 0 <= question["answer"] < len(question["options"]), f"{path}: invalid answer"
        assert len(question["explanation"]) >= 30, f"{path}: shallow explanation"


def validate_registry() -> None:
    path = ROOT / "hub" / "lessons.json"
    lessons = load_json(path)
    assert len(lessons) == 12, "registry must contain the complete 12-course roadmap"
    assert [lesson["step"] for lesson in lessons] == list(range(1, 13))
    assert len({lesson["id"] for lesson in lessons}) == 12
    ready = [lesson for lesson in lessons if lesson["status"] == "ready"]
    assert [lesson["id"] for lesson in ready] == ["advanced-01", "advanced-02"]
    for lesson in lessons:
        assert lesson["status"] in {"ready", "planned"}
        assert len(lesson["outcomes"]) >= 3
        if lesson["status"] == "ready":
            for key in ("readme", "notebook", "lab", "checkpoint"):
                target = (ROOT / "hub" / lesson[key].split("#", 1)[0]).resolve()
                assert target.exists(), f"{path}: missing {key} target {target}"
        else:
            assert lesson["notebook"] is None and lesson["lab"] is None


def validate_assessments() -> None:
    lessons = load_json(ROOT / "hub" / "lessons.json")
    for lesson in lessons:
        if lesson["status"] != "ready":
            continue
        checkpoint_path = (ROOT / "hub" / lesson["checkpoint"]).resolve()
        checkpoint = load_json(checkpoint_path)
        assert checkpoint["passing_score"] == 80
        assert len(checkpoint["questions"]) >= 8
        validate_question_set(checkpoint_path, checkpoint["questions"])

    quiz_path = ROOT / "quiz" / "questions.json"
    quiz = load_json(quiz_path)
    assert len(quiz["questions"]) >= 12
    validate_question_set(quiz_path, quiz["questions"])
    ready_course_numbers = {
        lesson["id"].removeprefix("advanced-")
        for lesson in lessons
        if lesson["status"] == "ready"
    }
    quiz_course_numbers = {question["course"] for question in quiz["questions"]}
    assert ready_course_numbers <= quiz_course_numbers, "full quiz must cover every ready course"


def validate_notebooks() -> None:
    lessons = load_json(ROOT / "hub" / "lessons.json")
    expected = {
        (ROOT / "hub" / lesson["notebook"]).resolve()
        for lesson in lessons
        if lesson["status"] == "ready"
    }
    notebooks = list((ROOT / "curriculum").rglob("*.ipynb"))
    assert {path.resolve() for path in notebooks} == expected, (
        "each ready course should have exactly one registered canonical notebook"
    )
    for path in notebooks:
        notebook = load_json(path)
        assert notebook["nbformat"] == 4
        assert len(notebook["cells"]) >= 20
        assert any(cell["cell_type"] == "code" for cell in notebook["cells"])
        source = "\n".join(
            "".join(cell.get("source", [])) for cell in notebook["cells"]
        )
        assert not any(
            output.get("output_type") == "error"
            for cell in notebook["cells"]
            for output in cell.get("outputs", [])
        ), f"{path}: contains an executed error output"
        for marker in ("failure", "evaluate", "production", "authorization"):
            assert marker in source.lower(), f"{path}: missing {marker} teaching path"


def validate_markdown_links() -> None:
    errors: list[str] = []
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts or ".venv" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in LINK.findall(text):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                errors.append(f"{path.relative_to(ROOT)} -> {raw_target}")
    assert not errors, "broken local Markdown links:\n" + "\n".join(errors)


def validate_web_assets() -> None:
    required = (
        "hub/index.html",
        "hub/styles.css",
        "hub/app.js",
        "quiz/index.html",
        "quiz/styles.css",
        "quiz/quiz.js",
    )
    for item in required:
        assert (ROOT / item).exists(), f"missing web asset: {item}"


def main() -> None:
    validate_registry()
    validate_assessments()
    validate_notebooks()
    validate_markdown_links()
    validate_web_assets()
    print("Curriculum validation passed: registry, assessments, notebooks, links, and Hub assets.")


if __name__ == "__main__":
    main()
