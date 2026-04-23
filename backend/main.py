import json
import os
import secrets
import sys
import traceback
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import cloudinary
import cloudinary.uploader
import resend
import stripe
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pricing_config  # noqa: E402

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5500").rstrip("/")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001").rstrip("/")
DATABASE_URL = os.getenv("DATABASE_URL", "")

DESIGN_PLAN_CHECKOUT_URL = os.getenv("DESIGN_PLAN_CHECKOUT_URL", "").strip()
BUILD_PLAN_CHECKOUT_URL = os.getenv("BUILD_PLAN_CHECKOUT_URL", "").strip()
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()

PACKAGE_ID_SIGNATURE_PLAN = "signature_plan"
PACKAGE_ID_PREMIUM_PLAN = "premium_plan"
LEGACY_PACKAGE_ID_DESIGN_PLAN = "design_plan"
LEGACY_PACKAGE_ID_BUILD_PLAN = "build_plan"

DESIGNER_STATUS_SUBMITTED = "submitted"
DESIGNER_STATUS_NEW = "new"
DESIGNER_STATUS_UNDER_REVIEW = "under_review"
DESIGNER_STATUS_RESPONDED = "responded"
DESIGNER_STATUS_CHECKOUT_SENT = "checkout_sent"
DESIGNER_STATUS_CONVERTED_SIGNATURE = "converted_signature_plan"
DESIGNER_STATUS_CONVERTED_PREMIUM = "converted_premium_plan"
DESIGNER_STATUS_CLOSED = "closed"

ALLOWED_DESIGNER_STATUSES = frozenset(
    {
        DESIGNER_STATUS_SUBMITTED,
        DESIGNER_STATUS_NEW,
        DESIGNER_STATUS_UNDER_REVIEW,
        DESIGNER_STATUS_RESPONDED,
        DESIGNER_STATUS_CHECKOUT_SENT,
        DESIGNER_STATUS_CONVERTED_SIGNATURE,
        DESIGNER_STATUS_CONVERTED_PREMIUM,
        DESIGNER_STATUS_CLOSED,
    }
)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "").strip()
raw_admin_emails = os.getenv("ADMIN_NOTIFICATION_EMAILS", "")
ADMIN_NOTIFICATION_EMAILS = [v.strip() for v in raw_admin_emails.split(",") if v.strip()]

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "").strip()
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "").strip()
CLOUDINARY_UPLOAD_FOLDER = (
    os.getenv("CLOUDINARY_UPLOAD_FOLDER", "")
    or os.getenv("CLOUDINARY_UPOLOAD_FOLDER", "northshore-gardens/questionnaires")
).strip("/")
CONTACT_CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_CONTACT_FOLDER", "northshore-gardens/contact").strip("/")

db_pool: ConnectionPool | None = None
MAX_PHOTOS = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
BASE_DIR = Path(__file__).resolve().parent
EMAIL_TEMPLATES_DIR = BASE_DIR / "email_templates"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://northshoregardens.studio",
        "https://www.northshoregardens.studio",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_pool() -> ConnectionPool:
    global db_pool
    if db_pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is missing.")
        db_pool = ConnectionPool(
            conninfo=DATABASE_URL,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            open=False,
            timeout=10,
        )
        db_pool.open()
        db_pool.wait()
    return db_pool


def init_db() -> None:
    """Create/extend tables and indexes. Safe for existing databases (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS intakes (
                    id BIGSERIAL PRIMARY KEY,
                    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    source TEXT NOT NULL DEFAULT 'intake',
                    answers JSONB NOT NULL DEFAULT '{}'::jsonb,
                    answers_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    ref_code TEXT,
                    admin_photos JSONB NOT NULL DEFAULT '[]'::jsonb,
                    admin_email_sent_at TIMESTAMPTZ,
                    client_email_sent_at TIMESTAMPTZ
                );
                """
            )
            for stmt in (
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS public_token TEXT;",
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'intake';",
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS answers JSONB NOT NULL DEFAULT '{}'::jsonb;",
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS entry_intent TEXT NOT NULL DEFAULT 'unknown';",
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS source_page TEXT NOT NULL DEFAULT 'unknown';",
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS designer_status TEXT NOT NULL DEFAULT 'submitted';",
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS converted_at TIMESTAMPTZ;",
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS stripe_session_id TEXT;",
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS stripe_payment_status TEXT;",
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS answers_json JSONB NOT NULL DEFAULT '{}'::jsonb;",
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS ref_code TEXT;",
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS designer_notes TEXT;",
                "ALTER TABLE intakes ADD COLUMN IF NOT EXISTS admin_photos JSONB NOT NULL DEFAULT '[]'::jsonb;",
            ):
                cur.execute(stmt)
            for stmt in (
                "ALTER TABLE intakes DROP COLUMN IF EXISTS improve;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS off_value;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS off_other;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS look_value;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS sun_value;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS change_size;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS notes;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS client_name;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS client_email;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS client_city;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS client_zip;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS photo_urls;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS responded_at;",
                "ALTER TABLE intakes DROP COLUMN IF EXISTS checkout_sent_at;",
            ):
                cur.execute(stmt)
            cur.execute("DROP TABLE IF EXISTS intake_responses;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS intake_conversions (
                    id BIGSERIAL PRIMARY KEY,
                    intake_id BIGINT NOT NULL REFERENCES intakes(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    package_id TEXT NOT NULL,
                    stripe_session_id TEXT,
                    payment_status TEXT NOT NULL DEFAULT 'pending',
                    amount_cents INTEGER,
                    currency TEXT,
                    purchased_at TIMESTAMPTZ
                );
                """
            )
            cur.execute("DROP TABLE IF EXISTS contacts;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_events (
                    id BIGSERIAL PRIMARY KEY,
                    lead_id BIGINT NOT NULL REFERENCES intakes(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            cur.execute(
                "CREATE INDEX IF NOT EXISTS intakes_designer_status_idx ON intakes(designer_status);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS intake_conversions_intake_id_idx ON intake_conversions(intake_id);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS lead_events_lead_id_idx ON lead_events(lead_id, created_at);"
            )

        conn.commit()

    backfill_missing_intake_public_tokens()
    backfill_missing_ref_codes()

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS intakes_public_token_uidx ON intakes(public_token);"
            )
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS intakes_ref_code_uidx ON intakes(ref_code);")
        conn.commit()


def generate_public_token() -> str:
    """Return a URL-safe, non-guessable token suitable for links and emails."""
    return secrets.token_urlsafe(16)


def backfill_missing_intake_public_tokens() -> None:
    """Assign public_token to any intake row missing one (idempotent)."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM intakes
                WHERE public_token IS NULL OR TRIM(public_token) = ''
                ORDER BY id;
                """
            )
            rows = cur.fetchall()
            for row in rows:
                intake_id = row["id"]
                for _ in range(40):
                    token = generate_public_token()
                    cur.execute(
                        "SELECT 1 FROM intakes WHERE public_token = %s LIMIT 1;",
                        (token,),
                    )
                    if cur.fetchone():
                        continue
                    cur.execute(
                        "UPDATE intakes SET public_token = %s WHERE id = %s;",
                        (token, intake_id),
                    )
                    break
                else:
                    raise RuntimeError(
                        f"Could not assign unique public_token for intake id={intake_id}"
                    )
        conn.commit()


def backfill_missing_ref_codes() -> None:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intakes
                SET ref_code = 'NG-' || id::text
                WHERE ref_code IS NULL OR TRIM(ref_code) = '';
                """
            )
        conn.commit()


def escape_html(value: Any) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@lru_cache(maxsize=32)
def load_email_template(template_name: str) -> dict[str, str]:
    """
    Load an email template from backend/email_templates/<template_name>.json.
    JSON shape:
    {
      "subject": "... {placeholder} ...",
      "html": "... {placeholder} ..."
    }
    """
    template_path = EMAIL_TEMPLATES_DIR / f"{template_name}.json"
    try:
        raw = template_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(f"Email template not found: {template_path}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Email template is not valid JSON: {template_path}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"Email template must be an object: {template_path}")

    subject = data.get("subject")
    html = data.get("html")
    if not isinstance(subject, str) or not isinstance(html, str):
        raise RuntimeError(
            f"Email template must include string 'subject' and 'html': {template_path}"
        )

    return {"subject": subject, "html": html}


def render_email_template(template_name: str, context: dict[str, Any]) -> dict[str, str]:
    """Render subject and html with python format placeholders."""
    template = load_email_template(template_name)
    safe_context = _SafeFormatDict(
        {k: ("" if v is None else str(v)) for k, v in context.items()}
    )
    return {
        "subject": template["subject"].format_map(safe_context),
        "html": template["html"].format_map(safe_context),
    }


def sample_email_template_context(template_name: str) -> dict[str, Any]:
    """Sample values used by dev template preview endpoint."""
    if template_name == "admin_intake_notification":
        return {
            "client_name": "Jane Doe",
            "submitted_at_utc": "2026-04-17 18:30:00",
            "token_line": "<p><strong>Public token:</strong> demoToken123</p>",
            "client_email": "jane@example.com",
            "client_city": "Northbrook",
            "client_zip": "60062",
            "entry_intent": "quick_ideas",
            "source_page": "hero",
            "improve": "Front yard curb appeal",
            "off_value": "Feels empty near walkway",
            "off_other": "Need lower maintenance planting.",
            "look_value": "Natural, structured, calming",
            "sun_value": "Mixed sun and shade",
            "change_size": "Keep footprint similar",
            "notes": "Would like a more polished arrival feel.",
            "photo_items": (
                '<li><a href="https://example.com/photo-1.jpg">https://example.com/photo-1.jpg</a></li>'
                '<li><a href="https://example.com/photo-2.jpg">https://example.com/photo-2.jpg</a></li>'
            ),
        }
    if template_name == "client_intake_confirmation":
        return {
            "client_name": "Jane",
            "reference_line": "<p><strong>Reference:</strong> NSG-ABC123</p>",
        }
    if template_name == "admin_contact_notification":
        return {
            "name": "Jane Doe",
            "submitted_at_utc": "2026-04-17 18:30:00",
            "email": "jane@example.com",
            "message": "Hi team,<br>I would love help with a spring refresh.",
            "attachment_items": (
                '<li><a href="https://example.com/attach-1.jpg">https://example.com/attach-1.jpg</a></li>'
            ),
        }
    if template_name == "client_contact_confirmation":
        return {"name": "Jane"}
    if template_name == "admin_payment_confirmation":
        return {
            "client_name": "Jane Doe",
            "client_email": "jane@example.com",
            "public_token": "demoToken123",
            "reference": "NSG-DEMOTOKE",
            "package_name": "Signature Plan",
            "payment_status": "paid",
            "amount_display": "$99.00",
            "currency": "usd",
            "stripe_session_id": "cs_test_123",
            "purchased_at_utc": "2026-04-17 19:00:00",
        }
    if template_name == "client_payment_confirmation":
        return {
            "client_name": "Jane",
            "reference": "NSG-DEMOTOKE",
            "package_name": "Signature Plan",
            "amount_display": "$99.00",
        }
    raise HTTPException(status_code=404, detail=f"Unknown template: {template_name}")


def client_reference_label(public_token: str) -> str:
    """Human-facing reference derived from token (no raw DB id)."""
    prefix = "".join(c for c in public_token[:10] if c.isalnum()).upper()
    if len(prefix) < 4:
        prefix = public_token[:8].upper()
    return f"NSG-{prefix[:8]}"


def build_purchase_link(base_url: str, public_token: str, package_id: str) -> str:
    """
    Append lead (public_token) and package_id as query params to a checkout base URL.
    Fails gracefully: returns empty string if base_url is missing.
    """
    base = (base_url or "").strip()
    if not base:
        return ""
    parsed = urlparse(base)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["lead"] = [public_token]
    qs["package"] = [package_id]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )


def build_purchase_links_for_intake(public_token: str) -> dict[str, str]:
    """
    Build design/build checkout URLs with token embedded.
    Missing env base URLs yield empty strings for that slot (graceful).
    """
    signature_link = build_purchase_link(
        DESIGN_PLAN_CHECKOUT_URL, public_token, PACKAGE_ID_SIGNATURE_PLAN
    )
    premium_link = build_purchase_link(
        BUILD_PLAN_CHECKOUT_URL, public_token, PACKAGE_ID_PREMIUM_PLAN
    )
    return {
        "signature_plan": signature_link,
        "premium_plan": premium_link,
        # Backward-compatible aliases for older consumers.
        "design_plan": signature_link,
        "build_plan": premium_link,
    }


def update_intake_designer_status(intake_id: int, new_status: str) -> None:
    """Set designer_status on an intake (validated)."""
    if new_status not in ALLOWED_DESIGNER_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid designer_status: {new_status}")
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT designer_status FROM intakes WHERE id = %s LIMIT 1;", (intake_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Intake not found.")
            previous_status = row.get("designer_status")
            cur.execute(
                "UPDATE intakes SET designer_status = %s WHERE id = %s;",
                (new_status, intake_id),
            )
        conn.commit()
    add_lead_event(
        intake_id,
        "designer_status_updated",
        {"from": previous_status, "to": new_status},
    )


def get_intake_by_public_token(public_token: str) -> dict[str, Any] | None:
    """Load full intake row by public_token (internal use)."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM intakes WHERE public_token = %s LIMIT 1;
                """,
                (public_token.strip(),),
            )
            return cur.fetchone()


def get_intake_by_id(lead_id: int) -> dict[str, Any] | None:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM intakes WHERE id = %s LIMIT 1;", (lead_id,))
            return cur.fetchone()


def intake_answers(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    answers_v2 = row.get("answers") or {}
    if isinstance(answers_v2, dict) and answers_v2:
        return answers_v2
    answers_json = row.get("answers_json") or {}
    if isinstance(answers_json, dict):
        answers = answers_json.get("answers")
        if isinstance(answers, dict):
            return answers
    return {}


def intake_primary_email(row: dict[str, Any] | None) -> str:
    answers = intake_answers(row)
    return str(answers.get("email") or "").strip()


def intake_primary_name(row: dict[str, Any] | None) -> str:
    answers = intake_answers(row)
    return str(answers.get("name") or "Website visitor").strip() or "Website visitor"


def intake_photo_urls(row: dict[str, Any] | None) -> list[str]:
    answers = intake_answers(row)
    out: list[str] = []
    for value in answers.values():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.startswith("http"):
                    out.append(item)
    return out


def _append_client_photo_urls_from_value(raw: Any, seen: set[str], out: list[str]) -> None:
    """Normalize list-of-URLs or a single URL string from answers.*"""
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.startswith("http") and item not in seen:
                seen.add(item)
                out.append(item)
    elif isinstance(raw, str) and raw.startswith("http") and raw not in seen:
        seen.add(raw)
        out.append(raw)


def client_yard_photo_urls(row: dict[str, Any] | None) -> list[str]:
    """Client-submitted image URLs from answers (intake + contact).

    Intake uploads use the `photos` field; the backend also copies into `yard_photos`
    when possible. We read both, plus contact `attachments`. Does not use `admin_photos`.
    """
    answers = intake_answers(row) if row else {}
    if not isinstance(answers, dict):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for key in ("yard_photos", "photos", "attachments"):
        _append_client_photo_urls_from_value(answers.get(key), seen, out)
    return out


def intake_admin_photo_urls(row: dict[str, Any] | None) -> list[str]:
    if not row:
        return []
    raw = row.get("admin_photos")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, str) and x.startswith("http")]
    return []


def add_lead_event(lead_id: int, event_type: str, event_data: dict[str, Any] | None = None) -> None:
    payload = event_data or {}
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lead_events (lead_id, event_type, event_data)
                VALUES (%s, %s, %s::jsonb);
                """,
                (lead_id, event_type, json.dumps(payload)),
            )
        conn.commit()


def get_lead_events(lead_id: int) -> list[dict[str, Any]]:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, lead_id, event_type, event_data, created_at
                FROM lead_events
                WHERE lead_id = %s
                ORDER BY created_at ASC;
                """,
                (lead_id,),
            )
            return cur.fetchall()


def intake_public_summary(row: dict[str, Any]) -> dict[str, Any]:
    """Safe-ish summary for GET /intakes/{public_token} (admin-oriented; no secrets beyond lead data)."""
    return {
        "id": row.get("id"),
        "ref_code": row.get("ref_code"),
        "public_token": row.get("public_token"),
        "source": row.get("source"),
        "submitted_at": row.get("submitted_at"),
        "answers": intake_answers(row),
        "answers_v2": row.get("answers"),
        "photo_urls": intake_photo_urls(row),
        "answers_json": row.get("answers_json"),
        "designer_status": row.get("designer_status"),
        "entry_intent": row.get("entry_intent"),
        "source_page": row.get("source_page"),
        "converted_at": row.get("converted_at"),
        "stripe_payment_status": row.get("stripe_payment_status"),
        "admin_email_sent_at": row.get("admin_email_sent_at"),
        "client_email_sent_at": row.get("client_email_sent_at"),
    }


def record_intake_conversion(
    public_token: str,
    package_id: str,
    stripe_session_id: str | None = None,
    payment_status: str = "paid",
    amount_cents: int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    """
    Record a purchase against an intake (e.g. future Stripe webhook).
    Updates intake conversion fields and designer_status by package.
    """
    token = public_token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="public_token is required.")
    normalized_package_id = package_id.strip().lower()
    if normalized_package_id == LEGACY_PACKAGE_ID_DESIGN_PLAN:
        normalized_package_id = PACKAGE_ID_SIGNATURE_PLAN
    elif normalized_package_id == LEGACY_PACKAGE_ID_BUILD_PLAN:
        normalized_package_id = PACKAGE_ID_PREMIUM_PLAN

    if normalized_package_id not in (PACKAGE_ID_SIGNATURE_PLAN, PACKAGE_ID_PREMIUM_PLAN):
        raise HTTPException(
            status_code=400,
            detail="package_id must be signature_plan or premium_plan.",
        )

    row = get_intake_by_public_token(token)
    if not row:
        raise HTTPException(status_code=404, detail="Intake not found.")

    intake_id = row["id"]
    new_designer_status = (
        DESIGNER_STATUS_CONVERTED_SIGNATURE
        if normalized_package_id == PACKAGE_ID_SIGNATURE_PLAN
        else DESIGNER_STATUS_CONVERTED_PREMIUM
    )

    pool = get_pool()
    inserted_new_conversion = False
    with pool.connection() as conn:
        with conn.cursor() as cur:
            conv: dict[str, Any] | None = None
            if stripe_session_id:
                cur.execute(
                    """
                    SELECT id, created_at FROM intake_conversions
                    WHERE stripe_session_id = %s
                    LIMIT 1;
                    """,
                    (stripe_session_id,),
                )
                conv = cur.fetchone()
            if not conv:
                cur.execute(
                    """
                    INSERT INTO intake_conversions (
                        intake_id, package_id, stripe_session_id, payment_status,
                        amount_cents, currency, purchased_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id, created_at;
                    """,
                    (
                        intake_id,
                        normalized_package_id,
                        stripe_session_id,
                        payment_status,
                        amount_cents,
                        currency,
                    ),
                )
                conv = cur.fetchone()
                inserted_new_conversion = True

            cur.execute(
                """
                UPDATE intakes
                SET
                    converted_at = NOW(),
                    stripe_session_id = COALESCE(%s, stripe_session_id),
                    stripe_payment_status = %s,
                    designer_status = %s
                WHERE id = %s;
                """,
                (stripe_session_id, payment_status, new_designer_status, intake_id),
            )
        conn.commit()

    if inserted_new_conversion:
        try:
            add_lead_event(
                intake_id,
                "plan_purchased",
                {
                    "package_id": normalized_package_id,
                    "stripe_session_id": stripe_session_id or "",
                    "payment_status": payment_status,
                },
            )
        except Exception:
            pass

    return {
        "conversion_id": conv["id"],
        "intake_id": intake_id,
        "package_id": normalized_package_id,
        "created_at": conv["created_at"],
        "designer_status": new_designer_status,
    }


def configure_cloudinary() -> None:
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        raise RuntimeError("Cloudinary config is missing.")
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )


def configure_stripe() -> None:
    """Initialize Stripe client; endpoints validate missing config gracefully."""
    if STRIPE_SECRET_KEY:
        stripe.api_key = STRIPE_SECRET_KEY


def ensure_stripe_checkout_config() -> None:
    missing = []
    if not STRIPE_SECRET_KEY:
        missing.append("STRIPE_SECRET_KEY")
    if not FRONTEND_URL:
        missing.append("FRONTEND_URL")
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Stripe checkout is not configured. Missing: {', '.join(missing)}",
        )


def ensure_stripe_webhook_config() -> None:
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Stripe webhook is not configured (missing STRIPE_SECRET_KEY or STRIPE_WEBHOOK_SECRET).",
        )


def _checkout_session_metadata_dict(session: Any) -> dict[str, str]:
    raw = _checkout_session_field(session, "metadata")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {str(k): "" if v is None else str(v) for k, v in raw.items()}
    try:
        return {str(k): "" if v is None else str(v) for k, v in dict(raw).items()}
    except Exception:
        return {}


def public_token_and_package_from_checkout_session(session: Any) -> tuple[str, str]:
    """Read public_token + package_id from session metadata, with client_reference_id fallback."""
    md = _checkout_session_metadata_dict(session)
    public_token = (md.get("public_token") or "").strip()
    package_id_raw = (md.get("package_id") or "").strip()
    cref = (_checkout_session_field(session, "client_reference_id") or "").strip()
    if "|" in cref:
        ct, cp = cref.split("|", 1)
        public_token = public_token or ct.strip()
        package_id_raw = package_id_raw or cp.strip()
    elif cref and not public_token:
        public_token = cref.strip()
    return public_token, package_id_raw


def normalize_checkout_package_id(raw_package_id: str) -> str:
    package_id = (raw_package_id or "").strip().lower()
    if package_id == LEGACY_PACKAGE_ID_DESIGN_PLAN:
        return PACKAGE_ID_SIGNATURE_PLAN
    if package_id == LEGACY_PACKAGE_ID_BUILD_PLAN:
        return PACKAGE_ID_PREMIUM_PLAN
    if package_id not in (PACKAGE_ID_SIGNATURE_PLAN, PACKAGE_ID_PREMIUM_PLAN):
        raise HTTPException(
            status_code=400,
            detail="package_id must be signature_plan or premium_plan.",
        )
    return package_id


def package_checkout_config(package_id: str) -> tuple[str, int]:
    """Stripe line item name and ``unit_amount`` in cents (USD); from ``pricing.json``."""
    try:
        plans = pricing_config.load_pricing()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="Server pricing file is missing. Add pricing.json at the repository root.",
        ) from exc
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Server pricing configuration is invalid: {exc}",
        ) from exc
    row = plans.get(package_id)
    if not row:
        raise HTTPException(status_code=400, detail="Invalid package_id.")
    return (row["product_name"], row["amount_cents"])


def ensure_email_service() -> None:
    if not RESEND_API_KEY or not RESEND_FROM_EMAIL:
        raise RuntimeError("Resend config is missing.")
    resend.api_key = RESEND_API_KEY


def package_display_name(package_id: str) -> str:
    if package_id == PACKAGE_ID_SIGNATURE_PLAN:
        return "Signature Plan"
    if package_id == PACKAGE_ID_PREMIUM_PLAN:
        return "Premium Plan"
    return package_id


def format_amount_display(amount_cents: int | None, currency: str | None) -> str:
    if amount_cents is None:
        return "N/A"
    curr = (currency or "usd").lower()
    if curr == "usd":
        return f"${amount_cents / 100:.2f}"
    return f"{amount_cents / 100:.2f} {curr.upper()}"


def send_admin_intake_email(payload: dict[str, Any]) -> bool:
    if not ADMIN_NOTIFICATION_EMAILS:
        return False
    ensure_email_service()

    photo_items = "".join(
        f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a></li>'
        for url in payload["photo_urls"]
    )
    token_line = ""
    if payload.get("public_token"):
        token_line = f"<p><strong>Public token:</strong> {escape_html(payload['public_token'])}</p>"
    rendered = render_email_template(
        "admin_intake_notification",
        {
            "client_name": escape_html(payload.get("client_name") or "Website visitor"),
            "submitted_at_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "token_line": token_line,
            "client_email": escape_html(payload.get("client_email") or ""),
            "client_city": escape_html(payload.get("client_city") or "—"),
            "client_zip": escape_html(payload.get("client_zip") or "—"),
            "entry_intent": escape_html(payload.get("entry_intent", "")),
            "source_page": escape_html(payload.get("source_page", "")),
            "improve": escape_html(payload.get("improve") or "—"),
            "off_value": escape_html(payload.get("off_value") or "—"),
            "off_other": escape_html(payload.get("off_other") or "—"),
            "look_value": escape_html(payload.get("look_value") or "—"),
            "sun_value": escape_html(payload.get("sun_value") or "—"),
            "change_size": escape_html(payload.get("change_size") or "—"),
            "notes": escape_html(payload.get("notes") or "—"),
            "photo_items": photo_items,
        },
    )
    resend.Emails.send(
        {
            "from": f"Northshore Gardens Studio <{RESEND_FROM_EMAIL}>",
            "to": ADMIN_NOTIFICATION_EMAILS,
            "reply_to": payload.get("client_email") or None,
            "subject": rendered["subject"],
            "html": rendered["html"],
        }
    )
    return True


def send_client_confirmation_email(
    client_name: str, client_email: str, public_token: str | None = None
) -> bool:
    """Send intake confirmation; optional lightweight reference derived from public_token (not raw DB id)."""
    ensure_email_service()
    ref_html = ""
    if public_token:
        ref = client_reference_label(public_token)
        ref_html = f"<p><strong>Reference:</strong> {escape_html(ref)}</p>"
    rendered = render_email_template(
        "client_intake_confirmation",
        {
            "client_name": escape_html(client_name),
            "reference_line": ref_html,
        },
    )
    resend.Emails.send(
        {
            "from": f"Northshore Gardens Studio <{RESEND_FROM_EMAIL}>",
            "to": [client_email],
            "subject": rendered["subject"],
            "html": rendered["html"],
        }
    )
    return True


def send_admin_contact_email(payload: dict[str, Any]) -> bool:
    if not ADMIN_NOTIFICATION_EMAILS:
        return False
    ensure_email_service()

    attachment_items = "".join(
        f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a></li>'
        for url in payload["attachment_urls"]
    )
    rendered = render_email_template(
        "admin_contact_notification",
        {
            "name": escape_html(payload["name"]),
            "submitted_at_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "email": escape_html(payload["email"]),
            "message": escape_html(payload["message"]).replace("\n", "<br>"),
            "attachment_items": attachment_items or "<li>No attachments</li>",
        },
    )
    resend.Emails.send(
        {
            "from": f"Northshore Gardens Studio <{RESEND_FROM_EMAIL}>",
            "to": ADMIN_NOTIFICATION_EMAILS,
            "reply_to": payload["email"],
            "subject": rendered["subject"],
            "html": rendered["html"],
        }
    )
    return True


def send_client_contact_confirmation_email(name: str, email: str) -> bool:
    ensure_email_service()
    rendered = render_email_template(
        "client_contact_confirmation",
        {"name": escape_html(name)},
    )
    resend.Emails.send(
        {
            "from": f"Northshore Gardens Studio <{RESEND_FROM_EMAIL}>",
            "to": [email],
            "subject": rendered["subject"],
            "html": rendered["html"],
        }
    )
    return True


def send_admin_payment_confirmation_email(payload: dict[str, Any]) -> bool:
    if not ADMIN_NOTIFICATION_EMAILS:
        return False
    ensure_email_service()
    rendered = render_email_template(
        "admin_payment_confirmation",
        {
            "client_name": escape_html(payload["client_name"]),
            "client_email": escape_html(payload["client_email"]),
            "public_token": escape_html(payload["public_token"]),
            "reference": escape_html(payload["reference"]),
            "package_name": escape_html(payload["package_name"]),
            "payment_status": escape_html(payload["payment_status"]),
            "amount_display": escape_html(payload["amount_display"]),
            "currency": escape_html(payload["currency"]),
            "stripe_session_id": escape_html(payload["stripe_session_id"]),
            "purchased_at_utc": escape_html(payload["purchased_at_utc"]),
        },
    )
    resend.Emails.send(
        {
            "from": f"Northshore Gardens Studio <{RESEND_FROM_EMAIL}>",
            "to": ADMIN_NOTIFICATION_EMAILS,
            "reply_to": payload["client_email"],
            "subject": rendered["subject"],
            "html": rendered["html"],
        }
    )
    return True


def send_client_payment_confirmation_email(payload: dict[str, Any]) -> bool:
    ensure_email_service()
    rendered = render_email_template(
        "client_payment_confirmation",
        {
            "client_name": escape_html(payload["client_name"]),
            "reference": escape_html(payload["reference"]),
            "package_name": escape_html(payload["package_name"]),
            "amount_display": escape_html(payload["amount_display"]),
        },
    )
    resend.Emails.send(
        {
            "from": f"Northshore Gardens Studio <{RESEND_FROM_EMAIL}>",
            "to": [payload["client_email"]],
            "subject": rendered["subject"],
            "html": rendered["html"],
        }
    )
    return True


def validate_required_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"{field_name} is required.")
    return cleaned


def slugify(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.strip("-")
    return slug or "client"


@app.on_event("startup")
def startup() -> None:
    init_db()
    configure_cloudinary()
    configure_stripe()


@app.on_event("shutdown")
def shutdown() -> None:
    global db_pool
    if db_pool is not None:
        db_pool.close()
        db_pool = None


@app.get("/")
def root() -> dict[str, Any]:
    """Public API root (e.g. opening the Render URL in a browser). The site is on FRONTEND_URL."""
    return {
        "service": "Northshore Gardens API",
        "ok": True,
        "frontend": FRONTEND_URL or None,
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/dev/email-preview/{template_name}", response_class=HTMLResponse)
def dev_email_preview(template_name: str) -> str:
    """
    Dev-only preview for email templates.
    """
    context = sample_email_template_context(template_name)
    rendered = render_email_template(template_name, context)
    escaped_subject = escape_html(rendered["subject"])
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Email Preview</title>"
        "<style>body{font-family:Arial,sans-serif;line-height:1.5;margin:24px;max-width:900px}"
        ".meta{background:#f7f7f7;border:1px solid #e5e5e5;padding:12px;border-radius:8px;margin-bottom:20px}"
        ".card{border:1px solid #e5e5e5;border-radius:8px;padding:20px}</style></head><body>"
        f"<div class='meta'><p><strong>Template:</strong> {escape_html(template_name)}</p>"
        f"<p><strong>Subject:</strong> {escaped_subject}</p></div>"
        f"<div class='card'>{rendered['html']}</div></body></html>"
    )


@app.post("/intake-submit")
async def intake_submit(request: Request) -> dict[str, Any]:
    form = await request.form()

    entry_intent_val = str(form.get("entry_intent") or "").strip() or "unknown"
    source_page_val = str(form.get("source_page") or "").strip() or "unknown"

    metadata_fields = {"entry_intent", "source_page"}
    text_answers: dict[str, str] = {}
    uploaded_urls_by_key: dict[str, list[str]] = {}

    # Parse text values and upload fields dynamically so questionnaire keys can evolve.
    for key in form.keys():
        if key in metadata_fields:
            continue
        values = form.getlist(key)
        upload_values = [v for v in values if isinstance(v, UploadFile)]
        if upload_values:
            if len(upload_values) > MAX_PHOTOS:
                raise HTTPException(status_code=400, detail=f"Upload up to {MAX_PHOTOS} photos.")
            uploaded_urls_by_key[key] = []
            continue
        first = values[0] if values else ""
        text_answers[key] = str(first or "").strip()

    resolved_email = (text_answers.get("email") or "").strip()
    if not resolved_email:
        raise HTTPException(status_code=400, detail="email is required.")
    if "@" not in resolved_email:
        raise HTTPException(status_code=400, detail="A valid email is required.")

    resolved_name = (text_answers.get("name") or "").strip()
    if not resolved_name:
        raise HTTPException(status_code=400, detail="name is required.")

    month_bucket = datetime.utcnow().strftime("%Y-%m")
    resolved_address = text_answers.get("address", "").strip()
    resolved_yard_goal = (text_answers.get("yard_goal") or text_answers.get("yardGoal") or "").strip()
    resolved_yard_notes = (text_answers.get("yard_notes") or text_answers.get("yardNotes") or "").strip()
    resolved_city = (text_answers.get("city") or "").strip()
    resolved_zip = (text_answers.get("zip") or "").strip()

    client_slug = slugify(resolved_name)
    folder = f"{CLOUDINARY_UPLOAD_FOLDER}/{month_bucket}/{client_slug}"

    uploaded_urls: list[str] = []
    for key in list(uploaded_urls_by_key.keys()):
        files = [v for v in form.getlist(key) if isinstance(v, UploadFile)]
        for upload in files:
            content_type = (upload.content_type or "").lower()
            if not content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Only image uploads are allowed.")

            file_bytes = await upload.read()
            if len(file_bytes) > MAX_FILE_BYTES:
                raise HTTPException(status_code=400, detail=f"Each photo must be <= {MAX_FILE_BYTES // (1024 * 1024)}MB.")

            try:
                upload_result = cloudinary.uploader.upload(
                    file_bytes,
                    folder=folder,
                    resource_type="image",
                    filename_override=upload.filename or "yard-photo",
                    use_filename=True,
                    unique_filename=True,
                    overwrite=False,
                )
                url = upload_result["secure_url"]
                uploaded_urls_by_key[key].append(url)
                uploaded_urls.append(url)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Photo upload failed: {exc}") from exc

    answers_payload = {
        "schema_version": 2,
        "answers": {
            **text_answers,
            **uploaded_urls_by_key,
            "email": resolved_email,
            "name": resolved_name,
        },
    }
    if resolved_address:
        answers_payload["answers"]["address"] = resolved_address
    if "yard_photos" not in answers_payload["answers"]:
        answers_payload["answers"]["yard_photos"] = (
            uploaded_urls_by_key.get("photos")
            or uploaded_urls_by_key.get("yard_photos")
            or uploaded_urls
        )

    payload = {
        "client_name": resolved_name,
        "client_email": resolved_email,
        "client_city": resolved_city or "—",
        "client_zip": resolved_zip or "—",
        "improve": resolved_yard_goal or "—",
        "notes": resolved_yard_notes or "—",
        "photo_urls": uploaded_urls,
        "entry_intent": entry_intent_val,
        "source_page": source_page_val,
        "answers_json": answers_payload,
        "answers": answers_payload.get("answers", {}),
    }

    pool = get_pool()
    public_token = ""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for _ in range(40):
                candidate = generate_public_token()
                cur.execute(
                    "SELECT 1 FROM intakes WHERE public_token = %s LIMIT 1;",
                    (candidate,),
                )
                if cur.fetchone():
                    continue
                public_token = candidate
                break
            else:
                raise HTTPException(
                    status_code=500, detail="Could not allocate a unique public token."
                )

            cur.execute(
                """
                INSERT INTO intakes (
                    source, answers, answers_json, public_token, entry_intent, source_page, designer_status
                )
                VALUES (
                    'intake', %(answers)s::jsonb, %(answers_json)s::jsonb, %(public_token)s, %(entry_intent)s, %(source_page)s, 'submitted'
                )
                RETURNING id;
                """,
                {
                    **payload,
                    "answers": json.dumps(payload["answers"]),
                    "answers_json": json.dumps(answers_payload),
                    "public_token": public_token,
                    "entry_intent": entry_intent_val,
                    "source_page": source_page_val,
                },
            )
            row = cur.fetchone()
            intake_id = row["id"]
            cur.execute(
                "UPDATE intakes SET ref_code = %s WHERE id = %s AND (ref_code IS NULL OR TRIM(ref_code) = '');",
                (f"NG-{intake_id}", intake_id),
            )
        conn.commit()

    try:
        add_lead_event(
            intake_id,
            "lead_submitted",
            {
                "email": resolved_email,
                "name": resolved_name,
                "entry_intent": entry_intent_val,
                "source_page": source_page_val,
                "photo_count": len(uploaded_urls),
            },
        )
    except Exception:
        # non-blocking internal timeline event
        pass

    payload["public_token"] = public_token
    payload["entry_intent"] = entry_intent_val
    payload["source_page"] = source_page_val

    admin_sent = False
    client_sent = False
    try:
        admin_sent = send_admin_intake_email(payload)
    except Exception:
        admin_sent = False

    try:
        client_sent = send_client_confirmation_email(resolved_name, resolved_email, public_token)
    except Exception:
        client_sent = False

    if admin_sent or client_sent:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intakes
                    SET
                      admin_email_sent_at = CASE WHEN %(admin_sent)s THEN NOW() ELSE admin_email_sent_at END,
                      client_email_sent_at = CASE WHEN %(client_sent)s THEN NOW() ELSE client_email_sent_at END
                    WHERE id = %(intake_id)s
                    """,
                    {
                        "admin_sent": admin_sent,
                        "client_sent": client_sent,
                        "intake_id": intake_id,
                    },
                )
            conn.commit()

    return {
        "ok": True,
        "intake_id": intake_id,
        "public_token": public_token,
        "photo_count": len(uploaded_urls),
        "admin_email_sent": admin_sent,
        "client_email_sent": client_sent,
    }


@app.post("/contact-submit")
async def contact_submit(
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    attachments: list[UploadFile] = File(default=[]),
) -> dict[str, Any]:
    name = validate_required_text(name, "name")
    email = validate_required_text(email, "email")
    message = validate_required_text(message, "message")

    if "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required.")
    if len(attachments) > MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"Upload up to {MAX_PHOTOS} attachments.")

    month_bucket = datetime.utcnow().strftime("%Y-%m")
    person_slug = slugify(name)
    folder = f"{CONTACT_CLOUDINARY_FOLDER}/{month_bucket}/{person_slug}"

    uploaded_urls: list[str] = []
    for attachment in attachments:
        content_type = (attachment.content_type or "").lower()
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Only image attachments are supported.")

        file_bytes = await attachment.read()
        if len(file_bytes) > MAX_FILE_BYTES:
            raise HTTPException(status_code=400, detail=f"Each attachment must be <= {MAX_FILE_BYTES // (1024 * 1024)}MB.")

        try:
            upload_result = cloudinary.uploader.upload(
                file_bytes,
                folder=folder,
                resource_type="image",
                filename_override=attachment.filename or "contact-attachment",
                use_filename=True,
                unique_filename=True,
                overwrite=False,
            )
            uploaded_urls.append(upload_result["secure_url"])
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Attachment upload failed: {exc}") from exc

    payload = {
        "name": name,
        "email": email,
        "message": message,
        "attachment_urls": uploaded_urls,
    }

    answers = {
        "name": name,
        "email": email,
        "message": message,
    }
    if uploaded_urls:
        answers["attachments"] = uploaded_urls

    pool = get_pool()
    public_token = ""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for _ in range(40):
                candidate = generate_public_token()
                cur.execute("SELECT 1 FROM intakes WHERE public_token = %s LIMIT 1;", (candidate,))
                if cur.fetchone():
                    continue
                public_token = candidate
                break
            else:
                raise HTTPException(status_code=500, detail="Could not allocate a unique public token.")
            cur.execute(
                """
                INSERT INTO intakes (source, answers, answers_json, public_token, designer_status)
                VALUES ('contact', %(answers)s::jsonb, %(answers_json)s::jsonb, %(public_token)s, %(designer_status)s)
                RETURNING id;
                """,
                {
                    "answers": json.dumps(answers),
                    "answers_json": json.dumps({"schema_version": 2, "answers": answers}),
                    "public_token": public_token,
                    "designer_status": DESIGNER_STATUS_NEW,
                },
            )
            row = cur.fetchone()
            lead_id = row["id"]
            cur.execute(
                "UPDATE intakes SET ref_code = %s WHERE id = %s AND (ref_code IS NULL OR TRIM(ref_code) = '');",
                (f"NG-{lead_id}", lead_id),
            )
        conn.commit()

    try:
        add_lead_event(
            lead_id,
            "contact_submitted",
            {"email": email, "attachment_count": len(uploaded_urls)},
        )
    except Exception:
        pass

    admin_sent = False
    client_sent = False
    try:
        admin_sent = send_admin_contact_email(payload)
    except Exception:
        admin_sent = False

    try:
        client_sent = send_client_contact_confirmation_email(name, email)
    except Exception:
        client_sent = False

    if admin_sent or client_sent:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intakes
                    SET
                      admin_email_sent_at = CASE WHEN %(admin_sent)s THEN NOW() ELSE admin_email_sent_at END,
                      client_email_sent_at = CASE WHEN %(client_sent)s THEN NOW() ELSE client_email_sent_at END
                    WHERE id = %(lead_id)s
                    """,
                    {
                        "admin_sent": admin_sent,
                        "client_sent": client_sent,
                        "lead_id": lead_id,
                    },
                )
            conn.commit()

    return {
        "ok": True,
        "lead_id": lead_id,
        "public_token": public_token,
        "attachment_count": len(uploaded_urls),
        "admin_email_sent": admin_sent,
        "client_email_sent": client_sent,
    }


class RecordConversionPayload(BaseModel):
    """Body for POST /intakes/{public_token}/record-conversion (temporary internal/admin endpoint)."""

    package_id: str = Field(..., min_length=1)
    stripe_session_id: str | None = None
    payment_status: str = "paid"
    amount_cents: int | None = None
    currency: str | None = None


class CheckoutSessionPayload(BaseModel):
    public_token: str = Field(..., min_length=1)
    package_id: str = Field(..., min_length=1)


class FinalizeCheckoutPayload(BaseModel):
    """Browser calls this after Stripe redirects to success_url (backup when webhooks cannot reach the server)."""

    session_id: str = Field(..., min_length=1)
    public_token: str | None = Field(default=None, description="Optional; must match session if provided.")


class AdminStatusPayload(BaseModel):
    designer_status: str = Field(..., min_length=1)


class AdminNotesPayload(BaseModel):
    notes: str = ""


class AdminCheckoutLinkPayload(BaseModel):
    mode: str = "plans_page"
    package_id: str | None = None


def create_plans_page_link(public_token: str) -> str:
    token = (public_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="public_token is required.")
    return f"{FRONTEND_URL}/plans.html?lead={token}"


def create_checkout_url_for_intake(public_token: str, package_id: str) -> str:
    ensure_stripe_checkout_config()
    token = (public_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="public_token is required.")
    normalized_package = normalize_checkout_package_id(package_id)
    intake = get_intake_by_public_token(token)
    if not intake:
        raise HTTPException(status_code=404, detail="Invalid intake token.")

    package_name, amount_cents = package_checkout_config(normalized_package)
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": package_name},
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            success_url=(
                f"{FRONTEND_URL}/checkout_success.html?lead={token}"
                "&session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=f"{FRONTEND_URL}/checkout_cancel.html?lead={token}",
            metadata={
                "public_token": token,
                "package_id": normalized_package,
                "client_email": intake_primary_email(intake),
            },
            client_reference_id=f"{token}|{normalized_package}"[:200],
            customer_email=intake_primary_email(intake) or None,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe checkout session failed: {exc}") from exc
    return session.url


@app.get("/intakes/{public_token}")
def get_intake_summary(public_token: str) -> dict[str, Any]:
    """
    Temporary internal/admin endpoint: summary of an intake by public_token.
    Does not expose raw numeric id in purchase links (none returned here for checkout).
    """
    row = get_intake_by_public_token(public_token)
    if not row:
        raise HTTPException(status_code=404, detail="Intake not found.")
    return {"ok": True, "intake": intake_public_summary(row)}


def _fmt_dt(value: Any) -> str:
    if not value:
        return "—"
    return str(value)


def _normalize_answers(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    answers_obj = intake_answers(row)
    return answers_obj, intake_photo_urls(row)


def _timeline_event_title(
    event_type: str | None, event_data: dict[str, Any] | None = None
) -> str:
    data = event_data if isinstance(event_data, dict) else {}
    if event_type == "plan_purchased":
        pkg = str(data.get("package_id") or "").strip().lower()
        if pkg == PACKAGE_ID_SIGNATURE_PLAN:
            return "Purchased Signature Plan"
        if pkg == PACKAGE_ID_PREMIUM_PLAN:
            return "Purchased Premium Plan"
        return "Plan purchase completed"
    if event_type == "admin_photo_added":
        return "Admin added a photo"
    if event_type == "lead_submitted":
        return "Questionnaire submitted"
    if event_type == "contact_submitted":
        return "Contact form submitted"
    return event_type or "event"


def _render_admin_leads_page(rows: list[dict[str, Any]]) -> str:
    body_rows = []
    for row in rows:
        answers, _ = _normalize_answers(row)
        client_name = intake_primary_name(row)
        email = answers.get("email") or "—"
        address = answers.get("address") or "—"
        source = (row.get("source") or "intake").strip().upper()
        ref_code = row.get("ref_code") or f"NG-{row.get('id')}"
        body_rows.append(
            "<tr onclick=\"window.location='/admin/leads/{id}'\">"
            "<td>{ref}</td><td>{source}</td><td>{name}</td><td>{email}</td><td>{address}</td><td>{created}</td><td>{status}</td></tr>".format(
                id=row.get("id"),
                ref=escape_html(ref_code),
                source=escape_html(source),
                name=escape_html(client_name),
                email=escape_html(email),
                address=escape_html(address),
                created=escape_html(_fmt_dt(row.get("submitted_at"))),
                status=escape_html(row.get("designer_status") or "submitted"),
            )
        )
    rows_html = "\n".join(body_rows) or "<tr><td colspan='7'>No leads yet.</td></tr>"
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Admin Leads</title>
<style>
body{{font-family:Inter,Arial,sans-serif;margin:24px;color:#2c2c28}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #e7e1d5;text-align:left}}
tr{{cursor:pointer}}tr:hover{{background:#faf7f1}}h1{{margin:0 0 16px}}
</style></head><body>
<h1>Leads</h1>
<table><thead><tr><th>ref_code</th><th>source</th><th>name</th><th>email</th><th>address</th><th>created_at</th><th>designer_status</th></tr></thead>
<tbody>{rows_html}</tbody></table></body></html>"""


def _render_admin_lead_detail_page(row: dict[str, Any], events: list[dict[str, Any]]) -> str:
    answers, _legacy_photos = _normalize_answers(row)
    display_name = intake_primary_name(row)
    client_photo_urls = client_yard_photo_urls(row)
    admin_photo_urls = intake_admin_photo_urls(row)
    source = (row.get("source") or "intake").strip().lower()
    lead_ref = row.get("ref_code") or f"NG-{row.get('id')}"
    message_html = ""
    if source == "contact":
        message_html = (
            "<p><strong>Message:</strong><br>"
            + escape_html(answers.get("message") or "—")
            + "</p>"
        )
    answers_items = []
    for key in sorted(answers.keys()):
        value = answers.get(key)
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        answers_items.append(
            f"<tr><td><strong>{escape_html(key)}</strong></td><td>{escape_html(value or '—')}</td></tr>"
        )
    answers_html = "\n".join(answers_items) or "<tr><td colspan='2'>No questionnaire answers.</td></tr>"
    client_photos_html = (
        "".join(
            f"<a href='{escape_html(url)}' target='_blank' rel='noopener'><img src='{escape_html(url)}' alt='Client photo' /></a>"
            for url in client_photo_urls
        )
        or "<p>No client photos.</p>"
    )
    admin_photos_html = (
        "".join(
            f"<a href='{escape_html(url)}' target='_blank' rel='noopener'><img src='{escape_html(url)}' alt='Admin-added photo' /></a>"
            for url in admin_photo_urls
        )
        or "<p>No admin-uploaded photos yet.</p>"
    )
    status_options = "".join(
        f"<option value='{s}' {'selected' if s == row.get('designer_status') else ''}>{s}</option>"
        for s in sorted(ALLOWED_DESIGNER_STATUSES)
    )
    submission_event_types = frozenset({"lead_submitted", "contact_submitted"})
    has_submission_event = any((ev.get("event_type") in submission_event_types) for ev in events)
    timeline_items: list[str] = []
    if not has_submission_event:
        if source == "contact":
            timeline_items.append(
                f"<li><strong>Submitted</strong> — {_fmt_dt(row.get('submitted_at'))}</li>"
            )
        else:
            timeline_items.append(
                f"<li><strong>Questionnaire received</strong> — {_fmt_dt(row.get('submitted_at'))}</li>"
            )
    for ev in events:
        data = ev.get("event_data") or {}
        if not isinstance(data, dict):
            data = {}
        etitle = escape_html(_timeline_event_title(ev.get("event_type"), data))
        timeline_items.append(
            "<li><strong>{title}</strong> — {dt}<br><small>{data}</small></li>".format(
                title=etitle,
                dt=escape_html(_fmt_dt(ev.get("created_at"))),
                data=escape_html(json.dumps(data, ensure_ascii=False)),
            )
        )
    timeline_html = "\n".join(timeline_items)
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Lead #{row.get("id")}</title>
<style>
body{{font-family:Inter,Arial,sans-serif;margin:24px;color:#2c2c28}}a{{color:#445735}}
.grid{{display:grid;grid-template-columns:1.2fr 1fr;gap:20px}}section{{border:1px solid #e7e1d5;border-radius:12px;padding:14px}}
table{{width:100%;border-collapse:collapse}}td{{padding:8px;border-bottom:1px solid #f0eadf;vertical-align:top}}
.photos{{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-start}}.photos img{{width:120px;height:90px;object-fit:cover;border-radius:8px;border:1px solid #ddd}}
.photo-block{{margin-top:12px}}.photo-block h4{{margin:0 0 6px;font-size:14px;color:#555}}
textarea{{width:100%;min-height:120px}}button{{padding:8px 12px}}.timeline li{{margin-bottom:10px}}
</style></head><body>
<p><a href='/admin/leads'>← Back to leads</a></p>
<h1>Lead {escape_html(lead_ref)} (#{row.get("id")})</h1>
<p><strong>Name:</strong> {escape_html(display_name)} &nbsp; <strong>Email:</strong> {escape_html(answers.get("email") or "—")} &nbsp; <strong>Status:</strong> {escape_html(row.get("designer_status") or "submitted")}</p>
<div class='grid'>
  <section>
    <h2>Intake Info</h2>
    {message_html}
    <table>{answers_html}</table>
    <h3>Photos</h3>
    <div class='photo-block'><h4>Client Photos</h4><div class='photos'>{client_photos_html}</div></div>
    <div class='photo-block'><h4>Added by You</h4><div class='photos'>{admin_photos_html}</div></div>
    <h3>Add Photo</h3>
    <p><input type='file' id='adminPhotoFile' accept='image/*' /> <button type='button' onclick='uploadAdminPhoto()'>Upload</button></p>
    <p id='adminPhotoMsg' style='font-size:13px;color:#666'></p>
  </section>
  <section>
    <h2>Status Control</h2>
    <select id='statusSelect'>{status_options}</select>
    <button onclick='saveStatus()'>Update Status</button>
    <h2>Private Notes</h2>
    <textarea id='notesBox'>{escape_html(row.get("designer_notes") or "")}</textarea>
    <button onclick='saveNotes()'>Save Notes</button>
    <h2>Generate Purchase Link</h2>
    <button onclick='generatePlansLink()'>Generate Plans Page Link</button>
    <details style='margin-top:8px'>
      <summary>Optional: direct plan checkout link</summary>
      <div style='margin-top:8px'>
        <select id='packageSelect'>
          <option value='{PACKAGE_ID_SIGNATURE_PLAN}'>Signature Plan</option>
          <option value='{PACKAGE_ID_PREMIUM_PLAN}'>Premium Plan</option>
        </select>
        <button onclick='generateCheckoutLink()'>Generate Direct Checkout Link</button>
      </div>
    </details>
    <div style='margin-top:8px'>
      <input id='checkoutLink' style='width:100%' readonly />
      <button onclick='copyCheckout()'>Copy</button>
    </div>
  </section>
</div>
<section style='margin-top:20px'><h2>Timeline</h2><ul class='timeline'>{timeline_html}</ul></section>
<script>
async function saveStatus(){{
  const res=await fetch('/admin/leads/{row.get("id")}/status',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{designer_status:document.getElementById('statusSelect').value}})}});
  if(!res.ok){{alert('Status update failed');return;}} location.reload();
}}
async function saveNotes(){{
  const res=await fetch('/admin/leads/{row.get("id")}/notes',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{notes:document.getElementById('notesBox').value}})}});
  if(!res.ok){{alert('Notes save failed');return;}} alert('Saved');
}}
async function generateCheckoutLink(){{
  const res=await fetch('/admin/leads/{row.get("id")}/generate-checkout-link',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{mode:'direct_checkout',package_id:document.getElementById('packageSelect').value}})}});
  if(!res.ok){{alert('Could not generate link');return;}}
  const payload=await res.json();
  document.getElementById('checkoutLink').value=payload.checkout_url||'';
}}
async function generatePlansLink(){{
  const res=await fetch('/admin/leads/{row.get("id")}/generate-checkout-link',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{mode:'plans_page'}})}});
  if(!res.ok){{alert('Could not generate link');return;}}
  const payload=await res.json();
  document.getElementById('checkoutLink').value=payload.checkout_url||'';
}}
async function copyCheckout(){{
  const inp=document.getElementById('checkoutLink');
  if(!inp.value) return;
  await navigator.clipboard.writeText(inp.value);
  alert('Copied');
}}
async function uploadAdminPhoto(){{
  const msg=document.getElementById('adminPhotoMsg');
  const input=document.getElementById('adminPhotoFile');
  msg.textContent='';
  const f=input.files&&input.files[0];
  if(!f){{alert('Choose an image file');return;}}
  const fd=new FormData();
  fd.append('file',f);
  const res=await fetch('/admin/leads/{row.get("id")}/upload-photo',{{method:'POST',body:fd}});
  if(!res.ok){{const t=await res.text();msg.textContent=t||'Upload failed';alert('Upload failed');return;}}
  location.reload();
}}
</script>
</body></html>"""


@app.get("/admin")
def admin_root_redirect() -> RedirectResponse:
    """So https://…/admin and https://…/admin/ land on the leads list (used via studio proxy or direct on Render)."""
    return RedirectResponse(url="/admin/leads", status_code=302)


@app.get("/admin/leads", response_class=HTMLResponse)
def admin_leads() -> str:
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ref_code, source, submitted_at, designer_status, answers, answers_json
                FROM intakes
                ORDER BY submitted_at DESC
                LIMIT 500;
                """
            )
            rows = cur.fetchall()
    return _render_admin_leads_page(rows)


@app.get("/admin/leads/{lead_id}", response_class=HTMLResponse)
def admin_lead_detail(lead_id: int) -> str:
    row = get_intake_by_id(lead_id)
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found.")
    events = get_lead_events(lead_id)
    return _render_admin_lead_detail_page(row, events)


@app.post("/admin/leads/{lead_id}/status")
def admin_update_lead_status(lead_id: int, payload: AdminStatusPayload) -> dict[str, Any]:
    row = get_intake_by_id(lead_id)
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found.")
    update_intake_designer_status(lead_id, payload.designer_status)
    refreshed = get_intake_by_id(lead_id)
    return {
        "ok": True,
        "lead_id": lead_id,
        "designer_status": refreshed.get("designer_status") if refreshed else payload.designer_status,
    }


@app.post("/admin/leads/{lead_id}/notes")
def admin_update_lead_notes(lead_id: int, payload: AdminNotesPayload) -> dict[str, Any]:
    row = get_intake_by_id(lead_id)
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found.")
    notes = (payload.notes or "").strip()
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE intakes SET designer_notes = %s WHERE id = %s;",
                (notes, lead_id),
            )
        conn.commit()
    add_lead_event(lead_id, "designer_notes_updated", {"notes_length": len(notes)})
    return {"ok": True, "lead_id": lead_id, "designer_notes": notes}


@app.post("/admin/leads/{lead_id}/upload-photo")
async def admin_upload_lead_photo(lead_id: int, file: UploadFile = File(...)) -> dict[str, Any]:
    row = get_intake_by_id(lead_id)
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found.")

    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are allowed.")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Each photo must be <= {MAX_FILE_BYTES // (1024 * 1024)}MB.",
        )

    month_bucket = datetime.utcnow().strftime("%Y-%m")
    lead_ref = slugify(str(row.get("ref_code") or f"lead-{lead_id}"))
    folder = f"{CLOUDINARY_UPLOAD_FOLDER}/admin/{month_bucket}/{lead_ref}"

    try:
        upload_result = cloudinary.uploader.upload(
            file_bytes,
            folder=folder,
            resource_type="image",
            filename_override=file.filename or "admin-yard-photo",
            use_filename=True,
            unique_filename=True,
            overwrite=False,
        )
        url = str(upload_result.get("secure_url") or "")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Photo upload failed: {exc}") from exc

    if not url.startswith("http"):
        raise HTTPException(status_code=502, detail="Photo upload did not return a URL.")

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intakes
                SET admin_photos = COALESCE(admin_photos, '[]'::jsonb) || jsonb_build_array(%s::text)
                WHERE id = %s;
                """,
                (url, lead_id),
            )
        conn.commit()

    add_lead_event(lead_id, "admin_photo_added", {"url": url})
    return {"ok": True, "lead_id": lead_id, "url": url}


@app.post("/admin/leads/{lead_id}/generate-checkout-link")
def admin_generate_checkout_link(
    lead_id: int, payload: AdminCheckoutLinkPayload
) -> dict[str, Any]:
    row = get_intake_by_id(lead_id)
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found.")
    token = (row.get("public_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Lead is missing public_token.")

    mode = (payload.mode or "plans_page").strip().lower()
    if mode == "plans_page":
        checkout_url = create_plans_page_link(token)
        package_used = None
    elif mode == "direct_checkout":
        package_id = payload.package_id or PACKAGE_ID_SIGNATURE_PLAN
        checkout_url = create_checkout_url_for_intake(token, package_id)
        package_used = package_id
    else:
        raise HTTPException(status_code=400, detail="mode must be plans_page or direct_checkout.")

    add_lead_event(
        lead_id,
        "checkout_link_generated",
        {"mode": mode, "package_id": package_used, "checkout_url": checkout_url},
    )
    return {"ok": True, "lead_id": lead_id, "checkout_url": checkout_url, "mode": mode}


@app.post("/create-checkout-session")
def create_checkout_session(payload: CheckoutSessionPayload) -> dict[str, str]:
    """
    Create Stripe checkout session for a plan selected from /plans?lead=PUBLIC_TOKEN.
    Uses public_token only (never intake_id in URLs).
    """
    checkout_url = create_checkout_url_for_intake(payload.public_token, payload.package_id)
    return {"checkout_url": checkout_url}


def _checkout_session_field(session: Any, name: str) -> Any:
    if isinstance(session, dict):
        return session.get(name)
    return getattr(session, name, None)


def conversion_exists_for_stripe_session(stripe_session_id: str | None) -> bool:
    sid = (stripe_session_id or "").strip()
    if not sid:
        return False
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM intake_conversions
                WHERE stripe_session_id = %s
                LIMIT 1;
                """,
                (sid,),
            )
            return cur.fetchone() is not None


def _send_stripe_payment_confirmation_emails(
    public_token: str,
    package_id: str,
    payment_status: str,
    amount_total: Any,
    currency: Any,
    stripe_session_id: str | None,
) -> None:
    intake_row = get_intake_by_public_token(public_token)
    if not intake_row:
        return
    payment_payload = {
        "client_name": intake_primary_name(intake_row) or "there",
        "client_email": intake_primary_email(intake_row) or "",
        "public_token": public_token,
        "reference": client_reference_label(public_token),
        "package_name": package_display_name(package_id),
        "payment_status": payment_status,
        "amount_display": format_amount_display(amount_total, currency),
        "currency": (currency or "usd"),
        "stripe_session_id": stripe_session_id or "",
        "purchased_at_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        if payment_payload["client_email"]:
            send_admin_payment_confirmation_email(payment_payload)
            send_client_payment_confirmation_email(payment_payload)
    except Exception as exc:
        print(f"[stripe_payment_emails] failed: {exc}")


@app.post("/finalize-stripe-checkout")
def finalize_stripe_checkout(payload: FinalizeCheckoutPayload) -> dict[str, Any]:
    """
    Record a completed Checkout Session using the Stripe API (browser redirect path).
    Use when `checkout.session.completed` webhooks are not delivered (e.g. local dev).
    """
    ensure_stripe_checkout_config()
    sid = payload.session_id.strip()
    try:
        session = stripe.checkout.Session.retrieve(sid)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not load Stripe session: {exc}") from exc

    pay_status = _checkout_session_field(session, "payment_status") or ""
    if pay_status != "paid":
        raise HTTPException(
            status_code=400,
            detail=f"Checkout session is not paid (status: {pay_status or 'unknown'}).",
        )

    public_token, package_id_raw = public_token_and_package_from_checkout_session(session)
    if not public_token or not package_id_raw:
        raise HTTPException(
            status_code=400,
            detail="Checkout session is missing public_token or package_id (metadata / client_reference_id).",
        )

    body_token = (payload.public_token or "").strip()
    if body_token and body_token != public_token:
        raise HTTPException(status_code=400, detail="Lead token does not match this checkout session.")

    package_id = normalize_checkout_package_id(package_id_raw)
    stripe_session_id = _checkout_session_field(session, "id")
    amount_total = _checkout_session_field(session, "amount_total")
    currency = _checkout_session_field(session, "currency")

    out = record_intake_conversion(
        public_token=public_token,
        package_id=package_id,
        stripe_session_id=stripe_session_id,
        payment_status="paid",
        amount_cents=amount_total,
        currency=currency,
    )
    _send_stripe_payment_confirmation_emails(
        public_token,
        package_id,
        "paid",
        amount_total,
        currency,
        stripe_session_id,
    )
    return {"ok": True, **out}


@app.post("/intakes/{public_token}/record-conversion")
def post_record_conversion(
    public_token: str, payload: RecordConversionPayload
) -> dict[str, Any]:
    """
    Temporary internal/admin endpoint: record a purchase against an intake (Stripe-ready).
    """
    out = record_intake_conversion(
        public_token=public_token,
        package_id=payload.package_id,
        stripe_session_id=payload.stripe_session_id,
        payment_status=payload.payment_status,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
    )
    return {"ok": True, **out}


@app.post("/stripe-webhook")
async def stripe_webhook(request: Request) -> dict[str, bool]:
    """Stripe webhook: signature-verified, idempotent, and fail-safe."""
    ensure_stripe_webhook_config()
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header.")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except Exception as exc:
        # Signature/format errors must be rejected for Stripe validation.
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {exc}") from exc

    event_type = _checkout_session_field(event, "type")
    print(f"[stripe_webhook] event_type={event_type!r}")
    if event_type != "checkout.session.completed":
        print("[stripe_webhook] skipped: unsupported event type")
        return {"ok": True}

    try:
        event_data = _checkout_session_field(event, "data")
        session = _checkout_session_field(event_data, "object") if event_data else None

        session_id = _checkout_session_field(session, "id")
        payment_status = _checkout_session_field(session, "payment_status") or "paid"
        amount_total = _checkout_session_field(session, "amount_total")
        currency = _checkout_session_field(session, "currency")

        print(
            "[stripe_webhook] checkout.session.completed"
            f" session_id={session_id!r} payment_status={payment_status!r}"
        )

        if conversion_exists_for_stripe_session(session_id):
            print(f"[stripe_webhook] skipped duplicate session_id={session_id!r}")
            return {"ok": True}

        public_token, package_id_raw = public_token_and_package_from_checkout_session(session)
        if not public_token or not package_id_raw:
            cref = _checkout_session_field(session, "client_reference_id")
            print(
                "[stripe_webhook] skipped: missing public_token/package_id"
                f" client_reference_id={cref!r} session_id={session_id!r}"
            )
            return {"ok": True}

        package_id = normalize_checkout_package_id(package_id_raw)

        record_intake_conversion(
            public_token=public_token,
            package_id=package_id,
            stripe_session_id=session_id,
            payment_status=payment_status,
            amount_cents=amount_total,
            currency=currency,
        )
        print(f"[stripe_webhook] processed session_id={session_id!r}")
        return {"ok": True}
    except Exception:
        print("[stripe_webhook] processing error (returning 200)")
        traceback.print_exc()
        return {"ok": True}
