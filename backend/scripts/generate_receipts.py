"""
Generate sample receipt/invoice PNG images + text sidecar files.
Run from the CS_Assistant root: python backend/scripts/generate_receipts.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# ── Setup paths ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
ATTACHMENTS_DIR = ROOT / "data" / "attachments"
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Receipt data ─────────────────────────────────────────────────────────────
RECEIPTS = [
    {
        "filename": "receipt_ORD1001",
        "order_id": "ORD-1001",
        "customer": "Sarah Mitchell",
        "item": "Wireless Keyboard",
        "qty": 1,
        "unit_price": 89.99,
        "total": 89.99,
        "date": "2026-08-28",
        "payment": "Visa ending 4242",
    },
    {
        "filename": "invoice_ORD1003",
        "order_id": "ORD-1003",
        "customer": "James Okafor",
        "item": "Laptop Stand",
        "qty": 1,
        "unit_price": 59.99,
        "total": 59.99,
        "date": "2026-09-01",
        "payment": "Mastercard ending 8823",
    },
    {
        "filename": "invoice_ORD1012",
        "order_id": "ORD-1012",
        "customer": "Priya Sharma",
        "item": "4K Monitor",
        "qty": 1,
        "unit_price": 749.99,    # Intentionally wrong — correct is 649.99
        "total": 749.99,
        "date": "2026-09-03",
        "payment": "PayPal",
    },
    {
        "filename": "receipt_ORD1007",
        "order_id": "ORD-1007",
        "customer": "Emily Watson",
        "item": "Mechanical Keyboard",
        "qty": 1,
        "unit_price": 149.99,
        "total": 149.99,
        "date": "2026-09-02",
        "payment": "Visa ending 9901",
    },
    {
        "filename": "receipt_ORD1005",
        "order_id": "ORD-1005",
        "customer": "Carlos Rivera",
        "item": "Wireless Mouse",
        "qty": 1,
        "unit_price": 49.99,
        "total": 49.99,
        "date": "2026-08-25",
        "payment": "Debit ending 3311",
    },
    {
        "filename": "receipt_ORD1015",
        "order_id": "ORD-1015",
        "customer": "Zoe Campbell",
        "item": "Ergonomic Chair",
        "qty": 1,
        "unit_price": 499.99,
        "total": 499.99,
        "date": "2026-09-07",
        "payment": "Amex ending 0077",
    },
    {
        "filename": "receipt_ORD1016",
        "order_id": "ORD-1016",
        "customer": "Michael Brown",
        "item": "Desk Lamp (Black)",
        "qty": 1,
        "unit_price": 45.99,
        "total": 45.99,
        "date": "2026-09-05",
        "payment": "Visa ending 5544",
    },
    {
        "filename": "invoice_ORD1020",
        "order_id": "ORD-1020",
        "customer": "Kevin Nguyen",
        "item": "External SSD 1TB",
        "qty": 1,
        "unit_price": 119.99,
        "total": 119.99,
        "date": "2026-09-09",
        "payment": "Bank Transfer",
    },
]


def generate_text_content(r: dict) -> str:
    """Generate the plain-text representation of a receipt."""
    tax = round(r["total"] * 0.10, 2)
    subtotal = round(r["total"] - tax, 2)
    return f"""
=====================================
         SupportAI STORE
       Customer Receipt / Invoice
=====================================
Order ID    : {r['order_id']}
Date        : {r['date']}
Customer    : {r['customer']}

-------------------------------------
ITEMS
-------------------------------------
{r['item']:30s}  x{r['qty']}   ${r['unit_price']:.2f}

-------------------------------------
Subtotal    :                ${subtotal:.2f}
GST (10%)   :                ${tax:.2f}
-------------------------------------
TOTAL PAID  :                ${r['total']:.2f}
-------------------------------------
Payment     : {r['payment']}

Thank you for your purchase!
For support: support@supportai.example.com
=====================================
""".strip()


def generate_png(r: dict, text_content: str):
    """Generate a PNG image of the receipt using Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    W, H = 420, 600
    img = Image.new("RGB", (W, H), color="#FAFAFA")
    draw = ImageDraw.Draw(img)

    # Dark header bar
    draw.rectangle([0, 0, W, 80], fill="#1a1a2e")
    draw.text((W // 2, 20), "SupportAI STORE", fill="white", anchor="mt",
              font=_font(18, bold=True))
    draw.text((W // 2, 48), "Official Receipt / Invoice", fill="#9a75ff", anchor="mt",
              font=_font(11))

    # Body background
    draw.rectangle([20, 90, W - 20, H - 20], fill="white",
                   outline="#e2e8f0", width=1)

    y = 105
    # Order ref line
    _label_value(draw, 30, y, "Order ID", r["order_id"], accent=True)
    y += 22
    _label_value(draw, 30, y, "Date", r["date"])
    y += 22
    _label_value(draw, 30, y, "Customer", r["customer"])
    y += 30

    # Divider
    draw.line([30, y, W - 30, y], fill="#e2e8f0", width=1)
    y += 12

    # Items header
    draw.text((30, y), "ITEM", fill="#718096", font=_font(9, bold=True))
    draw.text((W - 40, y), "AMOUNT", fill="#718096", font=_font(9, bold=True), anchor="ra")
    y += 18

    # Item row
    draw.text((30, y), r["item"], fill="#2d3748", font=_font(11))
    draw.text((W - 40, y), f"${r['unit_price']:.2f}", fill="#2d3748",
              font=_font(11), anchor="ra")
    y += 28

    # Divider
    draw.line([30, y, W - 30, y], fill="#e2e8f0", width=1)
    y += 12

    # Subtotal
    tax = round(r["total"] * 0.10, 2)
    subtotal = round(r["total"] - tax, 2)
    _label_value(draw, 30, y, "Subtotal", f"${subtotal:.2f}")
    y += 20
    _label_value(draw, 30, y, "GST (10%)", f"${tax:.2f}")
    y += 20

    # Total box
    draw.rectangle([20, y, W - 20, y + 40], fill="#1a1a2e")
    draw.text((35, y + 12), "TOTAL PAID", fill="#9a75ff", font=_font(12, bold=True))
    draw.text((W - 35, y + 12), f"${r['total']:.2f}", fill="white",
              font=_font(14, bold=True), anchor="ra")
    y += 55

    # Payment
    _label_value(draw, 30, y, "Payment", r["payment"])
    y += 30

    # Barcode-like visual
    draw.text((W // 2, H - 40), "||||  |||  |||||  ||  ||||  |  |||  ||||||",
              fill="#cccccc", font=_font(8), anchor="mm")
    draw.text((W // 2, H - 22), r["order_id"], fill="#aaaaaa",
              font=_font(8), anchor="mm")

    return img


def _font(size: int, bold: bool = False):
    """Try to load a system font, fall back to default."""
    try:
        from PIL import ImageFont
        font_names = ["arialbd.ttf" if bold else "arial.ttf",
                      "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
        for fn in font_names:
            try:
                return ImageFont.truetype(fn, size)
            except Exception:
                pass
        return ImageFont.load_default()
    except Exception:
        from PIL import ImageFont
        return ImageFont.load_default()


def _label_value(draw, x, y, label, value, accent=False):
    from PIL import ImageFont
    draw.text((x, y), f"{label}:", fill="#718096", font=_font(9))
    color = "#4f8ef7" if accent else "#2d3748"
    draw.text((x + 90, y), str(value), fill=color, font=_font(10, bold=accent))


def main():
    print(f"Generating {len(RECEIPTS)} receipt images in {ATTACHMENTS_DIR}...")
    for r in RECEIPTS:
        text = generate_text_content(r)
        # Save .txt sidecar (OCR fallback)
        txt_path = ATTACHMENTS_DIR / f"{r['filename']}.txt"
        txt_path.write_text(text, encoding="utf-8")
        print(f"  [txt] {txt_path.name}")

        # Save PNG
        try:
            img = generate_png(r, text)
            png_path = ATTACHMENTS_DIR / f"{r['filename']}.png"
            img.save(str(png_path))
            print(f"  [png] {png_path.name}")
        except ImportError:
            print("  [!] Pillow not installed — txt sidecar only (that's fine for demo)")
        except Exception as e:
            print(f"  [!] PNG failed: {e}")

    print(f"\nDone! {len(RECEIPTS)} receipts generated.")
    print("Text sidecar files (.txt) allow OCR fallback without PaddleOCR installed.")


if __name__ == "__main__":
    main()
