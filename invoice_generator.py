#!/usr/bin/env python3
"""invoice-generator: turn a JSON invoice into a clean PDF, in English, Arabic, or both.

    python invoice_generator.py invoice.json -o invoice.pdf --lang ar

The JSON describes seller, client, line items, tax/discount, currency and notes.
See examples/invoice-en.json and examples/invoice-ar.json.

Arabic rendering: reportlab does no shaping or bidi itself, so Arabic text is
reshaped (arabic_reshaper) and reordered (python-bidi), and mixed text is drawn
run by run - Arabic glyphs with Noto Naskh Arabic, everything else (Latin,
digits, ASCII punctuation) with Noto Sans.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONTS_DIR = Path(__file__).with_name("fonts")

STRINGS = {
    "en": {
        "title": "INVOICE", "number": "Invoice #", "date": "Date", "due": "Due date",
        "from": "From", "to": "Bill to",
        "col_item": "#", "col_desc": "Description", "col_qty": "Qty",
        "col_unit": "Unit price", "col_total": "Total",
        "subtotal": "Subtotal", "discount": "Discount", "tax": "Tax", "grand": "Total due",
        "notes": "Notes", "thanks": "Thank you for your business!",
    },
    "ar": {
        "title": "فاتورة", "number": "رقم الفاتورة", "date": "التاريخ", "due": "تاريخ الاستحقاق",
        "from": "من", "to": "إلى",
        "col_item": "م", "col_desc": "البيان", "col_qty": "الكمية",
        "col_unit": "سعر الوحدة", "col_total": "الإجمالي",
        "subtotal": "المجموع الفرعي", "discount": "الخصم", "tax": "الضريبة", "grand": "الإجمالي المستحق",
        "notes": "ملاحظات", "thanks": "شكرا لتعاملكم معنا!",
    },
}

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
ACCENT = colors.HexColor("#1f4e79")
LIGHT = colors.HexColor("#eef3f8")
AR_FONT, AR_BOLD, LAT_FONT, LAT_BOLD = "Naskh", "Naskh-Bold", "Lat", "Lat-Bold"

_ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
                  (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(AR_FONT, str(FONTS_DIR / "NotoNaskhArabic-Regular.ttf")))
    pdfmetrics.registerFont(TTFont(AR_BOLD, str(FONTS_DIR / "NotoNaskhArabic-Bold.ttf")))
    pdfmetrics.registerFont(TTFont(LAT_FONT, str(FONTS_DIR / "NotoSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont(LAT_BOLD, str(FONTS_DIR / "NotoSans-Bold.ttf")))


def _is_arabic_char(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _ARABIC_RANGES)


def to_visual(text: str) -> str:
    """Reshape and bidi-reorder only if the text actually contains Arabic."""
    if any(_is_arabic_char(ch) for ch in text):
        return get_display(arabic_reshaper.reshape(text))
    return text


def _runs(visual: str) -> list[tuple[str, bool]]:
    """Split a visual-order string into (run, is_arabic) pieces.

    Arabic-script characters keep the Naskh font; everything else (Latin
    letters, digits, ASCII punctuation) uses Noto Sans, because Naskh has no
    Latin glyphs. Spaces join the run they follow so words stay in one run.
    """
    runs: list[list] = []
    for ch in visual:
        if ch.isspace() and runs:
            runs[-1][0] += ch
            continue
        ar = _is_arabic_char(ch)
        if runs and ar == runs[-1][1]:
            runs[-1][0] += ch
        else:
            runs.append([ch, ar])
    return [(txt, ar) for txt, ar in runs]


def draw_mixed(c: canvas.Canvas, x: float, y: float, text: str, size: float = 11,
               bold: bool = False, color=colors.black, align: str = "left",
               max_width: float | None = None) -> None:
    """Draw text that may mix Arabic and Latin/digits, one font per run.

    x is the anchor: left edge for align='left', right edge for 'right',
    center for 'center'. Long text shrinks, then truncates, to fit max_width.
    """
    ar_f = AR_BOLD if bold else AR_FONT
    lat_f = LAT_BOLD if bold else LAT_FONT
    visual = to_visual(text)
    runs = _runs(visual)
    width = lambda: sum(pdfmetrics.stringWidth(r, ar_f if a else lat_f, size) for r, a in runs)
    if max_width is not None:
        while width() > max_width and size > 7:
            size -= 1
        while width() > max_width and len(text) > 4:
            text = text[:-2]
            visual = to_visual(text + "…")
            runs = _runs(visual)
    total = width()
    cursor = x if align == "left" else x - total if align == "right" else x - total / 2
    c.setFillColor(color)
    for run, is_ar in runs:
        f = ar_f if is_ar else lat_f
        c.setFont(f, size)
        c.drawString(cursor, y, run)
        cursor += pdfmetrics.stringWidth(run, f, size)


def money(amount: float, currency: str) -> str:
    return f"{amount:,.2f} {currency}"


def compute_totals(invoice: dict) -> dict:
    items = invoice["items"]
    subtotal = sum(float(i["qty"]) * float(i["unit_price"]) for i in items)
    discount = float(invoice.get("discount", 0))
    taxable = max(subtotal - discount, 0)
    tax_rate = float(invoice.get("tax_rate", 0))
    tax = round(taxable * tax_rate / 100, 2)
    grand = round(taxable + tax, 2)
    return {"subtotal": round(subtotal, 2), "discount": discount, "tax": tax, "grand": grand}


def draw_invoice_page(c: canvas.Canvas, invoice: dict, lang: str) -> None:
    s = STRINGS[lang]
    is_ar = lang == "ar"
    currency = invoice.get("currency", "EGP")
    totals = compute_totals(invoice)
    left, right = MARGIN, PAGE_W - MARGIN
    content_w = PAGE_W - 2 * MARGIN
    y = PAGE_H - MARGIN

    # header band
    c.setFillColor(ACCENT)
    c.rect(0, y - 12 * mm, PAGE_W, 18 * mm, stroke=0, fill=1)
    draw_mixed(c, right - 2 * mm if is_ar else left + 2 * mm, y - 6 * mm,
               s["title"], size=24, bold=True, color=colors.white,
               align="right" if is_ar else "left")
    num_line = f"{s['number']}: {invoice.get('number', '-')}"
    draw_mixed(c, left + 2 * mm if is_ar else right - 2 * mm, y - 6 * mm,
               num_line, size=11, color=colors.white,
               align="left" if is_ar else "right")
    y -= 24 * mm

    # dates
    side_align = "right" if is_ar else "left"
    anchor = right if is_ar else left
    meta = [(s["date"], invoice.get("date", ""))]
    if invoice.get("due_date"):
        meta.append((s["due"], invoice["due_date"]))
    for label, value in meta:
        draw_mixed(c, anchor, y, f"{label}: {value}", size=11, align=side_align)
        y -= 6 * mm
    y -= 4 * mm

    # parties: two side-by-side blocks; in Arabic "from" sits on the right
    gap = 10 * mm
    col_w = (content_w - gap) / 2
    parties = [(s["from"], invoice.get("seller", {})), (s["to"], invoice.get("client", {}))]
    for i, (label, party) in enumerate(parties):
        block_anchor = right - i * (col_w + gap) if is_ar else left + i * (col_w + gap)
        py = y
        draw_mixed(c, block_anchor, py, label, size=12, bold=True, color=ACCENT, align=side_align)
        py -= 6 * mm
        for line in [party.get("name", ""), party.get("address", ""),
                     party.get("phone", ""), party.get("email", "")]:
            if line:
                draw_mixed(c, block_anchor, py, line, size=10, align=side_align, max_width=col_w)
                py -= 5 * mm
    y -= 26 * mm

    # items table; for Arabic the whole column order is mirrored
    columns = [
        {"key": "col_item", "width": 12 * mm, "align": "center"},
        {"key": "col_desc", "width": 68 * mm, "align": "right" if is_ar else "left"},
        {"key": "col_qty", "width": 16 * mm, "align": "center"},
        {"key": "col_unit", "width": 37 * mm, "align": "right"},
        {"key": "col_total", "width": 37 * mm, "align": "right"},
    ]
    if is_ar:
        columns = columns[::-1]
    row_h = 8 * mm

    def cell_anchor(x_cell, w, align):
        if align == "left":
            return x_cell + 2 * mm
        if align == "right":
            return x_cell + w - 2 * mm
        return x_cell + w / 2

    def draw_row(values, y_top, header=False, fill=None):
        total_w = sum(col["width"] for col in columns)
        if fill:
            c.setFillColor(fill)
            c.rect(left, y_top - row_h, total_w, row_h, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#cccccc"))
        c.rect(left, y_top - row_h, total_w, row_h, stroke=1, fill=0)
        x = left
        for col, val in zip(columns, values):
            w, align = col["width"], col["align"]
            c.line(x, y_top, x, y_top - row_h)
            draw_mixed(c, cell_anchor(x, w, align), y_top - row_h + 2.5 * mm, str(val),
                       size=10, bold=header,
                       color=colors.white if header else colors.black,
                       align=align, max_width=w - 4 * mm)
            x += w
        c.line(left + total_w, y_top, left + total_w, y_top - row_h)

    draw_row([s[col["key"]] for col in columns], y, header=True, fill=ACCENT)
    y -= row_h
    for idx, item in enumerate(invoice["items"], 1):
        total = float(item["qty"]) * float(item["unit_price"])
        row_by_key = {"col_item": idx, "col_desc": item["description"], "col_qty": item["qty"],
                      "col_unit": money(float(item["unit_price"]), currency),
                      "col_total": money(total, currency)}
        if y < MARGIN + 40 * mm:
            c.showPage()
            y = PAGE_H - MARGIN
        draw_row([row_by_key[col["key"]] for col in columns], y,
                 fill=LIGHT if idx % 2 == 0 else None)
        y -= row_h
    y -= 8 * mm

    # totals block
    tot_anchor = right if not is_ar else left + 75 * mm
    tot_align = "right" if not is_ar else "left"
    rows = [(s["subtotal"], totals["subtotal"])]
    if totals["discount"]:
        rows.append((s["discount"], -totals["discount"]))
    if invoice.get("tax_rate"):
        rows.append((f"{s['tax']} {invoice['tax_rate']}%", totals["tax"]))
    rows.append((s["grand"], totals["grand"]))
    for label, val in rows:
        last = label == s["grand"]
        draw_mixed(c, tot_anchor, y, f"{label}: {money(val, currency)}",
                   size=13 if last else 11, bold=last,
                   color=ACCENT if last else colors.black, align=tot_align)
        y -= 7 * mm
    y -= 6 * mm

    if invoice.get("notes"):
        draw_mixed(c, anchor, y, f"{s['notes']}:", bold=True, align=side_align)
        y -= 6 * mm
        for line in invoice["notes"].splitlines():
            draw_mixed(c, anchor, y, line, size=10, align=side_align, max_width=content_w)
            y -= 5 * mm

    # footer
    draw_mixed(c, PAGE_W / 2, MARGIN - 4 * mm, s["thanks"], size=9,
               color=colors.grey, align="center")


def generate(invoice: dict, out_path: str, lang: str = "en") -> str:
    register_fonts()
    c = canvas.Canvas(out_path, pagesize=A4)
    c.setTitle(f"Invoice {invoice.get('number', '')}")
    langs = ["en", "ar"] if lang == "both" else [lang]
    for i, lg in enumerate(langs):
        if i:
            c.showPage()
        draw_invoice_page(c, invoice, lg)
    c.save()
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate a PDF invoice from a JSON file.")
    p.add_argument("json_file", type=Path, help="Invoice data (see examples/)")
    p.add_argument("-o", "--out", help="Output PDF path (default: <json>.pdf)")
    p.add_argument("--lang", choices=["en", "ar", "both"], default="en",
                   help="Invoice language; 'both' makes a 2-page PDF")
    args = p.parse_args(argv)

    invoice = json.loads(args.json_file.read_text(encoding="utf-8"))
    for key in ("seller", "client", "items"):
        if key not in invoice:
            p.error(f"missing required key: {key}")
    out = args.out or str(args.json_file.with_suffix(".pdf"))
    generate(invoice, out, lang=args.lang)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
