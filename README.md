# invoice-generator

Turn a JSON file into a clean, professional PDF invoice — in English, Arabic (full right-to-left layout), or both in one 2-page PDF. Built for freelancers: client and items in, invoice out.

## Setup

```bash
pip install -r requirements.txt
```

The Arabic and Latin fonts (Noto Naskh Arabic, Noto Sans) are bundled in `fonts/` under the SIL Open Font License, so nothing else to install.

## Usage

```bash
# English invoice
python invoice_generator.py examples/invoice-en.json -o invoice.pdf

# Arabic invoice (reshaped, bidi-correct, RTL layout)
python invoice_generator.py examples/invoice-ar.json -o invoice.pdf --lang ar

# Both languages in one PDF (page 1 English, page 2 Arabic)
python invoice_generator.py examples/invoice-ar.json -o invoice.pdf --lang both
```

## The JSON format

```json
{
  "number": "INV-2026-014",
  "date": "2026-11-25",
  "due_date": "2026-12-09",
  "currency": "EGP",
  "seller": {"name": "...", "address": "...", "phone": "...", "email": "..."},
  "client": {"name": "...", "address": "...", "phone": "..."},
  "items": [
    {"description": "Web app - milestone 1", "qty": 1, "unit_price": 8000},
    {"description": "Support hours", "qty": 3, "unit_price": 250}
  ],
  "discount": 250,
  "tax_rate": 14,
  "notes": "Payment by bank transfer within 14 days."
}
```

`discount`, `tax_rate` (percent), `due_date`, and `notes` are optional. Totals are computed for you: subtotal, discount, tax, and the grand total.

## How the Arabic rendering works

ReportLab does no text shaping or bidi by itself, so the generator reshapes Arabic with `arabic_reshaper`, reorders it with `python-bidi`, and draws the text run by run — Arabic glyphs in Noto Naskh Arabic, Latin letters and digits in Noto Sans — so mixed text like `INV-2026-014`, phone numbers, and emails render correctly inside Arabic invoices.

## Run the tests

```bash
python -m unittest discover -s tests -v
```

---

# مولد الفواتير

حوّل ملف JSON لفاتورة PDF شيك — بالإنجليزي، أو بالعربي (بتنسيق كامل من اليمين للشمال)، أو الاتنين مع بعض في ملف واحد من صفحتين. معمول للفريلانسرز: بيانات العميل والبنود تدخل، والفاتورة تطلع.

## التثبيت

```bash
pip install -r requirements.txt
```

الخطوط العربية واللاتينية متضمنة في فولدر `fonts/` برخصة SIL المفتوحة، فمفيش أي حاجة تانية تحتاجها.

## الاستخدام

```bash
# فاتورة عربي
python invoice_generator.py examples/invoice-ar.json -o invoice.pdf --lang ar

# فاتورة إنجليزي
python invoice_generator.py examples/invoice-en.json -o invoice.pdf

# الاتنين في ملف واحد
python invoice_generator.py examples/invoice-ar.json -o invoice.pdf --lang both
```

## شكل ملف البيانات

شوف `examples/invoice-ar.json` و`examples/invoice-en.json`. بتكتب بيانات البائع والعميل والبنود (الوصف، الكمية، سعر الوحدة)، واختياري خصم ونسبة ضريبة وملاحظات. الإجماليات بتحسب تلقائيا.

## إزاي بيشتغل مع العربي؟

مكتبة ReportLab متعملش تشكيل للحروف العربية من نفسها، فالأداة بتشكل النص بـ `arabic_reshaper` وترتبه بـ `python-bidi`، وترسم النص مقطع مقطع — الحروف العربية بخط Noto Naskh Arabic والأرقام والحروف اللاتينية بخط Noto Sans — عشان النصوص المختلطة زي أرقام التليفون والإيميلات تطلع صح جوه الفاتورة العربية.
