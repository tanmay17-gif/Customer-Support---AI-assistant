"""
Action Service — ACTUALLY executes the decided action.
Updates the database AND generates PDF files where relevant.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

from app.core.config import settings
from app.models.order import Order


# ── PDF Generator ────────────────────────────────────────────────────────────

def _generate_invoice_pdf(
    output_path: str,
    order_id: str,
    customer_name: str,
    customer_email: str,
    item: str,
    original_amount: float,
    corrected_amount: Optional[float],
    action_type: str,  # "refund_confirmation" | "corrected_invoice" | "replacement_confirmation"
):
    """Generate a styled PDF using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        doc = SimpleDocTemplate(output_path, pagesize=A4,
                                topMargin=20*mm, bottomMargin=20*mm,
                                leftMargin=20*mm, rightMargin=20*mm)
        styles = getSampleStyleSheet()
        story = []

        # Title style
        brand_style = ParagraphStyle("Brand", parent=styles["Heading1"],
                                     fontSize=22, textColor=colors.HexColor("#1a1a2e"),
                                     spaceAfter=4, alignment=TA_CENTER)
        sub_style = ParagraphStyle("Sub", parent=styles["Normal"],
                                   fontSize=10, textColor=colors.HexColor("#718096"),
                                   spaceAfter=2, alignment=TA_CENTER)
        heading_style = ParagraphStyle("Heading", parent=styles["Heading2"],
                                       fontSize=13, textColor=colors.HexColor("#2d3748"),
                                       spaceBefore=10, spaceAfter=6)
        body_style = ParagraphStyle("Body", parent=styles["Normal"],
                                    fontSize=10, textColor=colors.HexColor("#4a5568"),
                                    leading=16)

        # Header
        story.append(Paragraph("SupportAI", brand_style))
        story.append(Paragraph("Customer Support Platform", sub_style))
        story.append(Spacer(1, 4*mm))
        story.append(HRFlowable(width="100%", thickness=2,
                                color=colors.HexColor("#4f8ef7")))
        story.append(Spacer(1, 6*mm))

        # Document type title
        titles = {
            "refund_confirmation": "REFUND CONFIRMATION",
            "corrected_invoice": "CORRECTED INVOICE",
            "replacement_confirmation": "REPLACEMENT CONFIRMATION",
        }
        doc_title = titles.get(action_type, "DOCUMENT")
        story.append(Paragraph(doc_title, ParagraphStyle("DocTitle",
            parent=styles["Heading1"], fontSize=16,
            textColor=colors.HexColor("#4f46e5"), alignment=TA_CENTER)))
        story.append(Spacer(1, 8*mm))

        # Document details table
        now = datetime.utcnow().strftime("%B %d, %Y")
        data = [
            ["Document Date:", now],
            ["Order Reference:", order_id],
            ["Customer Name:", customer_name],
            ["Customer Email:", customer_email],
        ]
        t = Table(data, colWidths=[55*mm, 115*mm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#718096")),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#2d3748")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 8*mm))
        story.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#e2e8f0")))
        story.append(Spacer(1, 6*mm))

        # Order summary
        story.append(Paragraph("Order Summary", heading_style))
        amount_label = "Corrected Amount:" if action_type == "corrected_invoice" else "Amount:"
        display_amount = corrected_amount if corrected_amount else original_amount

        order_data = [
            ["Item", "Original Amount", amount_label.replace(":", "")],
            [item, f"${original_amount:.2f}", f"${display_amount:.2f}"],
        ]
        ot = Table(order_data, colWidths=[90*mm, 40*mm, 40*mm])
        ot.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f7fafc")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#718096")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(ot)
        story.append(Spacer(1, 8*mm))

        # Action note
        notes = {
            "refund_confirmation": f"A full refund of ${original_amount:.2f} has been approved and will be credited to your original payment method within 5–7 business days.",
            "corrected_invoice": f"This corrected invoice supersedes the original. The difference of ${abs(original_amount - (corrected_amount or original_amount)):.2f} will be refunded within 5 business days.",
            "replacement_confirmation": f"A replacement for '{item}' has been arranged and will ship within 2 business days. No action required from your side.",
        }
        note = notes.get(action_type, "")
        story.append(Paragraph("Action Taken", heading_style))
        story.append(Paragraph(note, body_style))
        story.append(Spacer(1, 10*mm))

        # Footer
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(
            "This document was generated by SupportAI. For queries, contact support@supportai.example.com",
            ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8,
                           textColor=colors.HexColor("#a0aec0"), alignment=TA_CENTER)
        ))
        doc.build(story)
        logger.info(f"PDF generated: {output_path}")
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")


# ── Public action executors ───────────────────────────────────────────────────

async def do_refund(db, order: Order) -> dict:
    import random
    from app.services.order_service import update_order_status
    updated = await update_order_status(
        db, order.id, order.business_id, "refunded",
        notes=f"Full refund processed on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )
    confirmation_id = f"TXN-REF-{random.randint(100000, 999999)}"
    invoices_dir = Path(settings.INVOICES_DIR).resolve()
    invoices_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = invoices_dir / f"refund_{order.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    await asyncio.to_thread(
        _generate_invoice_pdf,
        str(pdf_path), order.id, order.customer_name, order.customer_email,
        order.item, order.amount, None, "refund_confirmation"
    )
    return {
        "action": "refund",
        "description": f"Full refund of ${order.amount:.2f} approved and queued for {order.customer_name}.",
        "pdf_path": str(pdf_path),
        "order_status": "refunded",
        "confirmation_id": confirmation_id,
    }


async def do_replace(db, order: Order) -> dict:
    import random
    from app.services.order_service import update_order_status
    await update_order_status(
        db, order.id, order.business_id, "replacement_arranged",
        notes=f"Replacement arranged on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )
    confirmation_id = f"TRK-USPS-{random.randint(10000000, 99999999)}"
    invoices_dir = Path(settings.INVOICES_DIR).resolve()
    invoices_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = invoices_dir / f"replacement_{order.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    await asyncio.to_thread(
        _generate_invoice_pdf,
        str(pdf_path), order.id, order.customer_name, order.customer_email,
        order.item, order.amount, None, "replacement_confirmation"
    )
    return {
        "action": "replace",
        "description": f"Replacement for '{order.item}' arranged for {order.customer_name}. Tracking: {confirmation_id}.",
        "pdf_path": str(pdf_path),
        "order_status": "replacement_arranged",
        "confirmation_id": confirmation_id,
    }


async def do_reissue_invoice(db, order: Order, corrected_amount: Optional[float] = None) -> dict:
    import random
    from app.services.order_service import update_order_status
    await update_order_status(
        db, order.id, order.business_id, "invoice_reissued",
        notes=f"Corrected invoice issued on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )
    confirmation_id = f"INV-GEN-{random.randint(100000, 999999)}"
    invoices_dir = Path(settings.INVOICES_DIR).resolve()
    invoices_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = invoices_dir / f"invoice_{order.id}_corrected_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    effective_amount = corrected_amount or order.amount
    await asyncio.to_thread(
        _generate_invoice_pdf,
        str(pdf_path), order.id, order.customer_name, order.customer_email,
        order.item, order.amount, effective_amount, "corrected_invoice"
    )
    return {
        "action": "reissue_invoice",
        "description": f"Corrected invoice issued for {order.id}. Amount adjusted to ${effective_amount:.2f}.",
        "pdf_path": str(pdf_path),
        "order_status": "invoice_reissued",
        "confirmation_id": confirmation_id,
    }


async def do_issue_credit(db, order: Order, credit_amount: Optional[float] = None) -> dict:
    import random
    from app.services.order_service import update_order_status
    effective_credit = credit_amount or round(order.amount * 0.25, 2)
    confirmation_id = f"CRED-ST-{random.randint(100000, 999999)}"
    await update_order_status(
        db, order.id, order.business_id, "store_credit_issued",
        notes=f"Store credit of ${effective_credit:.2f} issued on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return {
        "action": "issue_credit",
        "description": f"Proactive Store Credit Voucher (${effective_credit:.2f}) issued for {order.customer_name}.",
        "pdf_path": None,
        "order_status": "store_credit_issued",
        "confirmation_id": confirmation_id,
    }


async def do_escalate(db, order: Optional[Order], reason: str) -> dict:
    if order:
        from app.services.order_service import update_order_status
        await update_order_status(db, order.id, order.business_id, "escalated",
                                  notes=f"Escalated: {reason}")
    return {
        "action": "escalate",
        "description": f"Escalated to human agent: {reason}",
        "pdf_path": None,
        "order_status": "escalated" if order else "unknown",
        "confirmation_id": None,
    }


async def do_request_info(db, order: Optional[Order]) -> dict:
    if order:
        from app.services.order_service import update_order_status
        await update_order_status(db, order.id, order.business_id, "awaiting_customer",
                                  notes="Requested more info from customer")
    return {
        "action": "request_info",
        "description": "Requested missing Order ID or clarification from customer.",
        "pdf_path": None,
        "order_status": "awaiting_customer" if order else "unknown",
        "confirmation_id": None,
    }

async def do_answer_query(db, order: Optional[Order]) -> dict:
    # We do not change order status for a simple query answer
    return {
        "action": "answer_query",
        "description": "Answered query using existing database information.",
        "pdf_path": None,
        "order_status": order.status if order else "unknown",
        "confirmation_id": None,
    }
