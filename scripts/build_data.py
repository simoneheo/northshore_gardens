from pathlib import Path
import json
import yaml

ROOT = Path(__file__).resolve().parent.parent
SITE_YAML = ROOT / "data" / "site.yaml"
OUT_JS = ROOT / "js" / "site-data.js"
GALLERY_DIR = ROOT / "assets" / "gallery"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def none_if_blank(value):
    if value in ("", None):
        return None
    return value


def find_image(project_dir: Path, stem: str) -> str | None:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = project_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate.relative_to(ROOT).as_posix()
    return None


def load_gallery_items() -> list[dict]:
    items = []

    if not GALLERY_DIR.exists():
        return items

    for project_dir in sorted(p for p in GALLERY_DIR.iterdir() if p.is_dir()):
        meta_file = project_dir / "meta.yaml"
        meta = load_yaml(meta_file) if meta_file.exists() else {}

        items.append({
            "id": meta.get("id", project_dir.name),
            "style": meta.get("style", ""),
            "location": meta.get("location", ""),
            "tags": meta.get("tags", []),
            "beforeImage": find_image(project_dir, "before"),
            "afterImage": find_image(project_dir, "after"),
            "featured": bool(meta.get("featured", False)),
            "sortOrder": int(meta.get("sort_order", 9999)),
        })

    items.sort(key=lambda x: (x["sortOrder"], x["location"], x["id"]))
    return items


def camel_site_data(raw: dict, gallery_items: list[dict]) -> dict:
    company = raw.get("company", {})
    hero = raw.get("hero", {})
    slider = raw.get("slider", {})
    home = raw.get("home", {})
    mini_hiw = home.get("mini_hiw", {})
    packages = raw.get("packages", {})
    how_it_works = raw.get("how_it_works", {})
    gallery = raw.get("gallery", {})
    about = raw.get("about", {})
    footer = raw.get("footer", {})

    logo_text = company.get("logo_text", {})

    return {
        "company": {
            "name": company.get("name", ""),
            "email": company.get("email", ""),
            "phone": company.get("phone", ""),
            "tagline": company.get("tagline", ""),
            "logoText": {
                "main": logo_text.get("main", ""),
                "accent": logo_text.get("accent", ""),
            },
        },

        "hero": {
            "eyebrow": hero.get("eyebrow", ""),
            "titleHtml": hero.get("title_html", ""),
            "subtext": hero.get("subtext", ""),
            "badges": hero.get("badges", []),
            "primaryCta": hero.get("primary_cta", {}),
            "secondaryCta": hero.get("secondary_cta", {}),
        },

        "slider": {
            "beforeLabel": slider.get("before_label", "Before"),
            "afterLabel": slider.get("after_label", "After"),
            "beforeAlt": slider.get("before_alt", "Before"),
            "afterAlt": slider.get("after_alt", "After"),
            "beforeImage": none_if_blank(slider.get("before_image")),
            "afterImage": none_if_blank(slider.get("after_image")),
        },

        "miniHowItWorks": {
            "eyebrow": mini_hiw.get("eyebrow", ""),
            "title": mini_hiw.get("title", ""),
            "subtext": mini_hiw.get("subtext", ""),
            "steps": mini_hiw.get("steps", []),
        },

        "packages": {
            "eyebrow": packages.get("eyebrow", ""),
            "title": packages.get("title", ""),
            "label": packages.get("label", ""),
            "name": packages.get("name", ""),
            "tagline": packages.get("tagline", ""),
            "includesLabel": packages.get("includes_label", ""),
            "deliverables": packages.get("deliverables", []),
            "noteHtml": packages.get("note_html", ""),
            "cartNoteHtml": packages.get("cart_note_html", ""),
            "lots": [
                {
                    "id": lot.get("id", ""),
                    "label": lot.get("label", ""),
                    "desc": lot.get("desc", ""),
                    "price": lot.get("price", 0),
                    "originalPrice": lot.get("original_price"),
                    "badge": lot.get("badge", ""),
                }
                for lot in packages.get("lots", [])
            ],
        },

        "howItWorks": {
            "eyebrow": how_it_works.get("eyebrow", ""),
            "title": how_it_works.get("title", ""),
            "subtext": how_it_works.get("subtext", ""),
            "steps": how_it_works.get("steps", []),
        },

        "gallery": {
            "eyebrow": gallery.get("eyebrow", ""),
            "title": gallery.get("title", ""),
            "subtext": gallery.get("subtext", ""),
            "note": gallery.get("note", ""),
            "items": gallery_items,
        },

        "about": {
            "eyebrow": about.get("eyebrow", ""),
            "titleHtml": about.get("title_html", ""),
            "paragraphs": about.get("paragraphs", []),
            "pillars": about.get("pillars", []),
        },

        "footer": {
            "copyright": footer.get("copyright", ""),
        },
    }


def main():
    raw = load_yaml(SITE_YAML)
    gallery_items = load_gallery_items()
    data = camel_site_data(raw, gallery_items)

    OUT_JS.write_text(
        "window.SITE_DATA = " + json.dumps(data, indent=2, ensure_ascii=False) + ";",
        encoding="utf-8",
    )

    print(f"Built {OUT_JS}")


if __name__ == "__main__":
    main()