#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

import yaml


REQUIRED_TOP_LEVEL_KEYS = ("hero", "contact")
REQUIRED_QUESTIONNAIRE_KEYS = ("intake",)
ALLOWED_STEP_TYPES = {"textarea", "upload", "text", "email"}


def _validate_site_content(data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        raise ValueError("site.yaml must contain a top-level mapping/object.")
    missing = [key for key in REQUIRED_TOP_LEVEL_KEYS if key not in data]
    if missing:
        raise ValueError(
            f"site.yaml is missing required top-level key(s): {', '.join(missing)}"
        )
    return data


def _load_site_yaml(input_path: Path) -> dict[str, object]:
    try:
        raw = input_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"Missing YAML file: {input_path}") from exc

    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed YAML in {input_path}: {exc}") from exc

    return _validate_site_content(parsed)


def build_site_data(input_path: Path, output_path: Path) -> None:
    content = _load_site_yaml(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "window.SITE_DATA = " + json.dumps(content, ensure_ascii=False, indent=2) + ";",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _load_yaml(path: Path, label: str) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"Missing YAML file: {path}") from exc
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed YAML in {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must contain a top-level mapping/object.")
    return parsed


def _validate_questionnaire_content(data: dict[str, object]) -> dict[str, object]:
    missing = [key for key in REQUIRED_QUESTIONNAIRE_KEYS if key not in data]
    if missing:
        raise ValueError(
            f"questionnaire.yaml is missing required top-level key(s): {', '.join(missing)}"
        )
    intake = data.get("intake")
    if not isinstance(intake, dict):
        raise ValueError("questionnaire.yaml intake must be an object.")
    steps = intake.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("questionnaire.yaml intake.steps must be a non-empty list.")
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"questionnaire.yaml intake.steps[{idx}] must be an object.")
        for req_key in ("key", "type", "label", "title"):
            if not isinstance(step.get(req_key), str) or not step.get(req_key):
                raise ValueError(
                    f"questionnaire.yaml intake.steps[{idx}] missing required string: {req_key}"
                )
        step_type = step.get("type")
        if step_type not in ALLOWED_STEP_TYPES:
            raise ValueError(
                f"questionnaire.yaml intake.steps[{idx}] type must be one of: {', '.join(sorted(ALLOWED_STEP_TYPES))}"
            )
    return data


def build_questionnaire_data(input_path: Path, output_path: Path) -> None:
    content = _load_yaml(input_path, "questionnaire.yaml")
    content = _validate_questionnaire_content(content)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "window.QUESTIONNAIRE_CONFIG = "
        + json.dumps(content, ensure_ascii=False, indent=2)
        + ";",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parent
    input_path = root / "site.yaml"
    output_path = root / "static" / "site-data.js"
    questionnaire_input_path = root / "questionnaire.yaml"
    questionnaire_output_path = root / "frontend" / "js" / "questionnaire-data.js"

    try:
        build_site_data(input_path, output_path)
        build_questionnaire_data(questionnaire_input_path, questionnaire_output_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("site-data.js built successfully")


if __name__ == "__main__":
    main()
