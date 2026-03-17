import os
import secrets
from typing import Optional

import resend
import stripe
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="Northshore Gardens API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
FRONTEND_URL = os.environ["FRONTEND_URL"].rstrip("/")
resend.api_key = os.getenv("RESEND_API_KEY")
ORDER_NOTIFICATION_EMAIL = os.getenv("ORDER_NOTIFICATION_EMAIL")

# Replace this with Postgres in the next step.
ORDERS: dict[str, dict] = {}


class CheckoutPayload(BaseModel):
    package_id: str
    package_name: str
    package_price: float
    customer_name: str
    customer_email: EmailStr
    customer_phone: str


class QuestionnairePayload(BaseModel):
    token: str
    address: str = ""
    yard_size: str = ""
    style_preferences: str = ""
    sun_shade: str = ""
    budget_notes: str = ""
    must_keep: str = ""
    inspiration_notes: str = ""


def send_questionnaire_email(to_email: str, customer_name: str, questionnaire_link: str) -> None:
    if not resend.api_key:
        print("RESEND_API_KEY missing. Skipping customer email.")
        return

    resend.Emails.send(
        {
            "from": os.getenv("EMAIL_FROM", "Northshore Gardens <onboarding@resend.dev>"),
            "to": [to_email],
            "subject": "Your Northshore Gardens questionnaire",
            "html": f"""
            <p>Hi {customer_name},</p>
            <p>Thank you for your purchase.</p>
            <p>Please complete your project questionnaire here:</p>
            <p><a href="{questionnaire_link}">{questionnaire_link}</a></p>
            <p>Once submitted, I'll review everything and start your design package.</p>
            """,
        }
    )


@app.get("/health")
def health_check():
    return {"ok": True}


@app.post("/create-checkout-session")
def create_checkout_session(payload: CheckoutPayload):
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=f"{FRONTEND_URL}/success.html?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/cancel.html",
            customer_email=payload.customer_email,
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Landscape Design Package — {payload.package_name}",
                        },
                        "unit_amount": int(payload.package_price * 100),
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "package_id": payload.package_id,
                "package_name": payload.package_name,
                "package_price": str(payload.package_price),
                "customer_name": payload.customer_name,
                "customer_email": payload.customer_email,
                "customer_phone": payload.customer_phone,
            },
        )
        return {"checkout_url": session.url}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook") from exc

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        token = secrets.token_urlsafe(24)

        order = {
            "payment_status": session.get("payment_status"),
            "stripe_session_id": session.get("id"),
            "customer_email": session["metadata"].get("customer_email"),
            "customer_name": session["metadata"].get("customer_name"),
            "customer_phone": session["metadata"].get("customer_phone"),
            "package_id": session["metadata"].get("package_id"),
            "package_name": session["metadata"].get("package_name"),
            "package_price": session["metadata"].get("package_price"),
            "questionnaire_token": token,
            "questionnaire_submitted": False,
        }
        ORDERS[token] = order

        questionnaire_link = f"{FRONTEND_URL}/questionnaire.html?token={token}"
        send_questionnaire_email(
            to_email=order["customer_email"],
            customer_name=order["customer_name"],
            questionnaire_link=questionnaire_link,
        )

        if ORDER_NOTIFICATION_EMAIL and resend.api_key:
            resend.Emails.send(
                {
                    "from": os.getenv("EMAIL_FROM", "Northshore Gardens <onboarding@resend.dev>"),
                    "to": [ORDER_NOTIFICATION_EMAIL],
                    "subject": "New Northshore Gardens order",
                    "html": f"""
                    <p>New order received.</p>
                    <p><strong>Name:</strong> {order['customer_name']}</p>
                    <p><strong>Email:</strong> {order['customer_email']}</p>
                    <p><strong>Phone:</strong> {order['customer_phone']}</p>
                    <p><strong>Package:</strong> {order['package_name']}</p>
                    <p><strong>Questionnaire link:</strong> <a href="{questionnaire_link}">open</a></p>
                    """,
                }
            )

    return {"ok": True}


@app.post("/questionnaire-submit")
def questionnaire_submit(payload: QuestionnairePayload):
    order = ORDERS.get(payload.token)
    if not order:
        raise HTTPException(status_code=404, detail="Invalid questionnaire token")

    order["questionnaire"] = payload.model_dump()
    order["questionnaire_submitted"] = True

    if ORDER_NOTIFICATION_EMAIL and resend.api_key:
        resend.Emails.send(
            {
                "from": os.getenv("EMAIL_FROM", "Northshore Gardens <onboarding@resend.dev>"),
                "to": [ORDER_NOTIFICATION_EMAIL],
                "subject": "Questionnaire submitted",
                "html": f"""
                <p>The client questionnaire was submitted.</p>
                <p><strong>Name:</strong> {order['customer_name']}</p>
                <p><strong>Email:</strong> {order['customer_email']}</p>
                <p><strong>Address:</strong> {payload.address}</p>
                <p><strong>Style:</strong> {payload.style_preferences}</p>
                """,
            }
        )

    return {"ok": True}
