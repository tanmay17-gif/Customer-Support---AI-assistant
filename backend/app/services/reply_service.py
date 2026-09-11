"""
Reply Service — renders the HTML email reply using the Jinja2 template.
Calls LLM to get body paragraphs and timeline steps, then injects into template.
"""
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from typing import Optional

from app.core.config import settings
from app.models.order import Order
from app.services.llm_service import GeminiLLMService


_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _get_jinja_env() -> Environment:
    return Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=False)


async def draft_reply(
    action: str,
    order: Optional[Order],
    customer_name: str,
    customer_email: str,
    original_email_body: str,
    action_summary: str,
    llm: GeminiLLMService,
    reference_id: str,
    attachment_paths: list[str] = None,
    business_id: str = "biz_tech",
) -> tuple[str, str, str]:
    """
    Returns (html_reply, plain_text_reply, reference_id).
    """
    # Fix name casing
    customer_name = customer_name.title() if customer_name else "Customer"

    order_dict = None
    if order:
        order_dict = {
            "id": order.id,
            "item": order.item,
            "amount": order.amount,
            "status": order.status,
            "customer_name": order.customer_name,
        }

    attachment_names = []
    if attachment_paths:
        import os
        attachment_names = [os.path.basename(p) for p in attachment_paths]

    company_name = "StyleBoutique" if business_id == "biz_apparel" else "TechGadgets Inc."

    # Ask LLM to draft the content
    try:
        content = await llm.draft_reply_content(
            action=action,
            order=order_dict,
            customer_name=customer_name,
            original_email_body=original_email_body,
            action_summary=action_summary,
            attachment_names=attachment_names,
            company_name=company_name,
        )
    except Exception as e:
        logger.warning(f"LLM reply draft failed: {e}")
        content = {
            "body_paragraph": f"We have reviewed your request and taken the following action: {action_summary} Please allow 3-5 business days for changes to take effect."
        }

    # Render Jinja2 template
    env = _get_jinja_env()
    template = env.get_template("email_reply.html")

    now = datetime.utcnow()
    
    ctx = {
        "subject": _subject_for_action(action, order),
        "order_id": order.id if order else None,
        "reference_id": reference_id,
        "date": now.strftime("%B %d, %Y"),
        "action_type": action,
        "customer_name": customer_name,
        "action_summary": action_summary,
        "item": order.item if order else None,
        "amount": order.amount if order else None,
        "new_status": _status_label(action),
        "body_paragraph": content.get("body_paragraph", ""),
        "cta_label": _cta_label(action),
        "cta_url": "#",
        "agent_name": "Support Team",
        "year": now.year,
        "brand_name": settings.BRAND_NAME,
        "brand_logo_url": settings.BRAND_LOGO_URL,
    }
    html = template.render(**ctx)

    # Plain text fallback
    plain = f"Dear {customer_name},\n\n" + content.get("body_paragraph", action_summary) + "\n\nWarm regards,\nSupportAI Customer Care"

    return html, plain, reference_id


def _subject_for_action(action: str, order: Optional[Order]) -> str:
    order_ref = f" — {order.id}" if order else ""
    subjects = {
        "refund": f"Your Refund Has Been Processed{order_ref}",
        "replace": f"Your Replacement Is On Its Way{order_ref}",
        "reissue_invoice": f"Your Corrected Invoice{order_ref}",
        "escalate": f"Your Request — Our Team Is On It{order_ref}",
    }
    return subjects.get(action, f"Update On Your Request{order_ref}")


def _status_label(action: str) -> str:
    return {
        "refund": "Refunded",
        "replace": "Replacement Arranged",
        "reissue_invoice": "Invoice Reissued",
        "escalate": "Escalated for Review",
    }.get(action, "Updated")


def _cta_label(action: str) -> Optional[str]:
    return {
        "refund": "View Refund Status",
        "replace": "Track Your Replacement",
        "reissue_invoice": "Download Invoice",
        "escalate": None,
    }.get(action)
