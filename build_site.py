#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from pricing_config import load_pricing


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


def _collect_gallery_items(gallery_dir: Path) -> list[dict[str, object]]:
    """Read each subfolder's meta.json; sort by ``order``. Image paths default to before/after-800.webp."""
    rows: list[tuple[int, str, dict[str, object]]] = []
    if not gallery_dir.is_dir():
        return []
    for sub in sorted(gallery_dir.iterdir()):
        if not sub.is_dir():
            continue
        meta_path = sub / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(raw, dict):
            continue
        order_val = raw.get("order")
        if isinstance(order_val, bool) or order_val is None:
            order = 999
        elif isinstance(order_val, int):
            order = order_val
        else:
            try:
                order = int(order_val)
            except (TypeError, ValueError):
                order = 999
        tags_raw = raw.get("tags")
        tags: list[str] = []
        if isinstance(tags_raw, list):
            tags = [t.strip() for t in tags_raw if isinstance(t, str) and t.strip()]
        slug = sub.name
        before_file = (
            raw["before_image"] if isinstance(raw.get("before_image"), str) else "before-800.webp"
        )
        after_file = (
            raw["after_image"] if isinstance(raw.get("after_image"), str) else "after-800.webp"
        )
        before_alt = raw["before_alt"] if isinstance(raw.get("before_alt"), str) else "Before"
        after_alt = raw["after_alt"] if isinstance(raw.get("after_alt"), str) else "After"
        before_label = (
            raw["before_label"] if isinstance(raw.get("before_label"), str) else "Before"
        )
        after_label = raw["after_label"] if isinstance(raw.get("after_label"), str) else "After"
        base = f"/assets/gallery/{slug}"
        item: dict[str, object] = {
            "slug": slug,
            "beforeSrc": f"{base}/{before_file}",
            "afterSrc": f"{base}/{after_file}",
            "beforeAlt": before_alt,
            "afterAlt": after_alt,
            "beforeLabel": before_label,
            "afterLabel": after_label,
            "tags": tags,
        }
        rows.append((order, slug, item))
    rows.sort(key=lambda r: (r[0], r[1]))
    return [r[2] for r in rows]


def build_site_data(input_path: Path, output_path: Path) -> None:
    content = _load_site_yaml(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "window.SITE_DATA = " + json.dumps(content, ensure_ascii=False, indent=2) + ";",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _build_frontend_site_data(content: dict[str, object]) -> dict[str, object]:
    """Flatten selected site.yaml fields to legacy frontend/js/site-data.js keys."""
    out: dict[str, object] = {}

    navigation = content.get("navigation")
    if isinstance(navigation, dict):
        links = navigation.get("links")
        if isinstance(links, dict):
            if isinstance(links.get("gallery"), str):
                out["navGallery"] = links["gallery"]
            if isinstance(links.get("how_it_works"), str):
                out["navHowItWorks"] = links["how_it_works"]
            if isinstance(links.get("why_us"), str):
                out["navWhyUs"] = links["why_us"]
            if isinstance(links.get("packages"), str):
                out["navPackages"] = links["packages"]
        if isinstance(navigation.get("cta"), str):
            out["navCta"] = navigation["cta"]

    for k in ("logoTextMain", "logoTextAccent", "logoTextStudio", "footerTagline"):
        if isinstance(content.get(k), str):
            out[k] = content[k]

    hero = content.get("hero")
    if isinstance(hero, dict):
        if isinstance(hero.get("eyebrow"), str):
            out["heroEyebrow"] = hero["eyebrow"]
        if isinstance(hero.get("title"), str):
            out["heroTitle"] = hero["title"]
        if isinstance(hero.get("subtext"), str):
            out["heroSubtext"] = hero["subtext"]
        cta = hero.get("cta")
        if isinstance(cta, dict):
            if isinstance(cta.get("primary"), str):
                out["heroPrimaryCta"] = cta["primary"]
            if isinstance(cta.get("secondary"), str):
                out["heroSecondaryCta"] = cta["secondary"]
            if isinstance(cta.get("tertiary"), str):
                out["heroTertiaryCta"] = cta["tertiary"]
            if isinstance(cta.get("microcopy"), str):
                out["heroCtaMicrocopy"] = cta["microcopy"]
        points = hero.get("points")
        if isinstance(points, list):
            if len(points) > 0 and isinstance(points[0], str):
                out["heroPoint1"] = points[0]
            if len(points) > 1 and isinstance(points[1], str):
                out["heroPoint2"] = points[1]
            if len(points) > 2 and isinstance(points[2], str):
                out["heroPoint3"] = points[2]

    gallery = content.get("gallery")
    if isinstance(gallery, dict):
        out["galleryEyebrow"] = (
            gallery["eyebrow"] if isinstance(gallery.get("eyebrow"), str) else "Gallery"
        )
        if isinstance(gallery.get("title"), str):
            out["galleryTitle"] = gallery["title"]
        if isinstance(gallery.get("intro"), str):
            out["galleryIntro"] = gallery["intro"]

    repo_root = Path(__file__).resolve().parent
    gallery_items = _collect_gallery_items(repo_root / "frontend" / "assets" / "gallery")
    if gallery_items:
        out["galleryItems"] = gallery_items

    how_it_works = content.get("how_it_works")
    if isinstance(how_it_works, dict):
        if isinstance(how_it_works.get("eyebrow"), str):
            out["howItWorksEyebrow"] = how_it_works["eyebrow"]
        if isinstance(how_it_works.get("title"), str):
            out["howItWorksTitle"] = how_it_works["title"]
        if isinstance(how_it_works.get("intro"), str):
            out["howItWorksIntro"] = how_it_works["intro"]
        steps = how_it_works.get("steps")
        if isinstance(steps, list):
            for idx in range(4):
                if idx < len(steps) and isinstance(steps[idx], dict):
                    title = steps[idx].get("title")
                    body = steps[idx].get("body")
                    if isinstance(title, str):
                        out[f"step{idx + 1}Title"] = title
                    if isinstance(body, str):
                        out[f"step{idx + 1}Body"] = body

    why_diff = content.get("why_this_is_different")
    if isinstance(why_diff, dict):
        if isinstance(why_diff.get("eyebrow"), str):
            out["whyEyebrow"] = why_diff["eyebrow"]
        if isinstance(why_diff.get("title"), str):
            out["whyTitle"] = why_diff["title"]
        if isinstance(why_diff.get("body"), str):
            out["whyBody"] = why_diff["body"]
        items = why_diff.get("items")
        if isinstance(items, list):
            for idx in range(5):
                if idx < len(items) and isinstance(items[idx], dict):
                    title = items[idx].get("title")
                    body = items[idx].get("body")
                    if isinstance(title, str):
                        out[f"diff{idx + 1}Title"] = title
                    if isinstance(body, str):
                        out[f"diff{idx + 1}Body"] = body

    packages = content.get("packages")
    if isinstance(packages, dict):
        if isinstance(packages.get("eyebrow"), str):
            out["packagesEyebrow"] = packages["eyebrow"]
        if isinstance(packages.get("title"), str):
            out["packagesTitle"] = packages["title"]
        if isinstance(packages.get("intro"), str):
            out["packagesIntro"] = packages["intro"]
        if isinstance(packages.get("cta"), str):
            out["packagesCta"] = packages["cta"]

        signature = packages.get("signature")
        if isinstance(signature, dict):
            if isinstance(signature.get("label"), str):
                out["package1Label"] = signature["label"]
            if isinstance(signature.get("title"), str):
                out["package1Title"] = signature["title"]
            if isinstance(signature.get("subtitle"), str):
                out["package1Subtitle"] = signature["subtitle"]
            sig_items = signature.get("items")
            if isinstance(sig_items, list):
                for idx in range(6):
                    if idx < len(sig_items) and isinstance(sig_items[idx], str):
                        out[f"package1Item{idx + 1}"] = sig_items[idx]
            if isinstance(signature.get("note"), str):
                out["package1Note"] = signature["note"]

        premium = packages.get("premium")
        if isinstance(premium, dict):
            if isinstance(premium.get("label"), str):
                out["package2Label"] = premium["label"]
            if isinstance(premium.get("title"), str):
                out["package2Title"] = premium["title"]
            if isinstance(premium.get("subtitle"), str):
                out["package2Subtitle"] = premium["subtitle"]
            pre_items = premium.get("items")
            if isinstance(pre_items, list):
                for idx in range(6):
                    if idx < len(pre_items) and isinstance(pre_items[idx], str):
                        out[f"package2Item{idx + 1}"] = pre_items[idx]
            if isinstance(premium.get("note"), str):
                out["package2Note"] = premium["note"]

    contact = content.get("contact")
    if isinstance(contact, dict):
        if isinstance(contact.get("title"), str):
            out["contactTitle"] = contact["title"]
        if isinstance(contact.get("body"), str):
            out["contactIntro"] = contact["body"]
        if isinstance(contact.get("trust"), str):
            out["contactTrust"] = contact["trust"]
        form = contact.get("form")
        if isinstance(form, dict):
            if isinstance(form.get("name_label"), str):
                out["contactNameLabel"] = form["name_label"]
            if isinstance(form.get("message_label"), str):
                out["contactMessageLabel"] = form["message_label"]
            if isinstance(form.get("email_label"), str):
                out["contactEmailLabel"] = form["email_label"]
            if isinstance(form.get("upload_label"), str):
                out["contactAttachmentLabel"] = form["upload_label"]
            if isinstance(form.get("submit_label"), str):
                out["contactSubmitButton"] = form["submit_label"]
        success = contact.get("success")
        if isinstance(success, dict):
            if isinstance(success.get("title"), str):
                out["contactSuccessTitle"] = success["title"]
            if isinstance(success.get("body"), str):
                out["contactSuccessBody"] = success["body"]

    _merge_plan_pricing_into_site_data(out)
    return out


def _merge_plan_pricing_into_site_data(out: dict[str, object]) -> None:
    """UI package prices from ``pricing.json`` (same source as Stripe in ``backend/main.py``)."""
    plans = load_pricing()
    out["package1Price"] = plans["signature_plan"]["display"]
    out["package2Price"] = plans["premium_plan"]["display"]


def build_frontend_site_data(input_path: Path, output_path: Path) -> None:
    content = _load_site_yaml(input_path)
    flat_content = _build_frontend_site_data(content)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "window.SITE_DATA = " + json.dumps(flat_content, ensure_ascii=False, indent=2) + ";",
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
    frontend_output_path = root / "frontend" / "js" / "site-data.js"
    questionnaire_input_path = root / "questionnaire.yaml"
    questionnaire_output_path = root / "frontend" / "js" / "questionnaire-data.js"

    try:
        build_frontend_site_data(input_path, frontend_output_path)
        build_questionnaire_data(questionnaire_input_path, questionnaire_output_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("site-data.js built successfully")


if __name__ == "__main__":
    main()
