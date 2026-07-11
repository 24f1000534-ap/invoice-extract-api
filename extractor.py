import re
from datetime import datetime


MONTHS = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "sept": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}


def parse_amount(raw: str):
    """Turn '1,40,000.00' or '2,199.00' or '395.82' into a float.
    Indian-style grouping (lakhs/crores) still works because we just
    strip every comma before converting."""
    if raw is None:
        return None
    cleaned = raw.replace(",", "").strip()
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def parse_date(raw: str):
    """Convert many date spellings into YYYY-MM-DD."""
    if not raw:
        return None
    raw = raw.strip()

    # Already ISO: 2026-01-22
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    # "15 March 2026" or "15 Mar 2026"
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)
    if m:
        d, mon, y = m.groups()
        mon_num = MONTHS.get(mon.lower())
        if mon_num:
            return f"{y}-{mon_num}-{int(d):02d}"

    # "March 15, 2026" or "March 15 2026"
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", raw)
    if m:
        mon, d, y = m.groups()
        mon_num = MONTHS.get(mon.lower())
        if mon_num:
            return f"{y}-{mon_num}-{int(d):02d}"

    # "15/03/2026" or "15-03-2026" (assume DD/MM/YYYY, common in India)
    m = re.match(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", raw)
    if m:
        d, mo, y = m.groups()
        try:
            return f"{y}-{int(mo):02d}-{int(d):02d}"
        except ValueError:
            return None

    return None


def find_first(patterns, text):
    """Try each regex in order, return the first captured group that matches."""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def extract_invoice_fields(text: str) -> dict:
    if not text or not text.strip():
        return {
            "invoice_no": None, "date": None, "vendor": None,
            "amount": None, "tax": None, "currency": None,
        }

    # --- invoice number ---
    invoice_no = find_first([
        r"Invoice\s*(?:No\.?|Number)\s*:?\s*([A-Za-z0-9\-/]+)",
        r"Invoice\s*#\s*:?\s*([A-Za-z0-9\-/]+)",
        r"(?:Bill|Receipt|Order|Folio|Voucher|Transaction|Doc(?:ument)?)\s*(?:No\.?|Number|ID|#)\s*:?\s*([A-Za-z0-9\-/]+)",
        r"Ref(?:erence)?\.?\s*(?:No\.?|Number)?\s*:\s*([A-Za-z0-9\-/]+)",
        r"\b([A-Z]{2,}[-/]\d{4}[-/][A-Za-z0-9]+)\b",  # e.g. NS/2026/778 or INV-2026-0041
        r"\b([A-Z]{2,6}[-/]\d{3,})\b",                # e.g. FL-8822, INV-0041
    ], text)

    # --- date ---
    date_raw = find_first([
        r"(?:Date|Issued|Invoice\s*Date)\s*:\s*([0-9A-Za-z ,/-]+)",
    ], text)
    date = parse_date(date_raw) if date_raw else None
    if date is None:
        date = parse_date(date_raw.split("\n")[0]) if date_raw else None

    # --- vendor ---
    vendor = find_first([
        r"Vendor\s*:\s*(.+)",
        r"Supplier\s*:\s*(.+)",
        r"^([A-Z][A-Za-z0-9&.,' ]+?)\s*[—-]\s*Tax\s*Invoice",  # "NovaSoft Solutions — Tax Invoice"
        r"From\s*:\s*(.+)",
    ], text)
    if vendor:
        vendor = vendor.split("\n")[0].strip()

    # --- subtotal (amount before tax) ---
    amount_raw = find_first([
        r"Sub[\s-]?total\s*:?\.*\s*(?:Rs\.?|INR|₹|\$|USD|€|EUR|£|GBP)?\s*([\d,]+\.\d{1,2})",
        r"Sub[\s-]?total\s*:?\.*\s*(?:Rs\.?|INR|₹|\$|USD|€|EUR|£|GBP)?\s*([\d,]+)",
        r"(?:Net\s*Amount|Taxable\s*(?:Value|Amount)|Base\s*(?:Price|Amount)|Pre[\s-]?tax\s*Amount|Amount\s*before\s*Tax|Principal(?:\s*Amount)?|Value|Price|Cost|Charge)\s*:?\.*\s*(?:Rs\.?|INR|₹|\$|USD|€|EUR|£|GBP)?\s*([\d,]+(?:\.\d{1,2})?)\s*/?-?",
        # bare "Amount:" but NOT "Total Amount"/"Grand Amount", and NOT immediately
        # followed on the SAME spot by "Due"/"Payable" (fixed: previously this
        # incorrectly scanned the whole rest of the document, not just this match)
        r"(?<!Total\s)(?<!Grand\s)\bAmount\b\s*:?\.*\s*(?!Due\b)(?!Payable\b)(?:Rs\.?|INR|₹|\$|USD|€|EUR|£|GBP)?\s*([\d,]+(?:\.\d{1,2})?)\s*/?-?",
    ], text)
    amount = parse_amount(amount_raw)

    # --- tax ---
    tax_raw = find_first([
        r"(?:IGST|CGST|SGST|GST|VAT|Tax)\s*\([\d.]+%\)\s*:?\.*\s*(?:Rs\.?|INR|₹|\$|USD|€|EUR|£|GBP)?\s*([\d,]+(?:\.\d{1,2})?)",
        r"(?:IGST|CGST|SGST|GST|VAT|Tax)\s*:?\.*\s*(?:Rs\.?|INR|₹|\$|USD|€|EUR|£|GBP)?\s*([\d,]+(?:\.\d{1,2})?)",
    ], text)
    tax = parse_amount(tax_raw)

    # --- fallback 1: derive subtotal from Total - Tax when no subtotal label matched ---
    if amount is None:
        total_raw = find_first([
            r"(?:Grand\s*Total|Total\s*(?:Due|Payable|Amount)?|Amount\s*(?:Due|Payable))\s*:?\.*\s*(?:Rs\.?|INR|₹|\$|USD|€|EUR|£|GBP)?\s*([\d,]+(?:\.\d{1,2})?)\s*/?-?",
        ], text)
        total = parse_amount(total_raw)
        if total is not None and tax is not None:
            amount = round(total - tax, 2)

    # --- fallback 2: last resort — grab the first standalone currency-looking
    # number in the text that isn't the tax value or part of a date, if we
    # still have nothing at all ---
    if amount is None:
        candidates = re.findall(
            r"(?:Rs\.?|INR|₹|\$|USD|€|EUR|£|GBP)\s*([\d,]+(?:\.\d{1,2})?)|\b(\d{2,}(?:,\d{2,3})*(?:\.\d{1,2})?)\b",
            text,
        )
        for a, b in candidates:
            val = parse_amount(a or b)
            if val is not None and val != tax:
                amount = val
                break

    # --- currency ---
    currency = find_first([
        r"Currency\s*:\s*([A-Za-z]{3})",
    ], text)
    if not currency:
        if re.search(r"Rs\.|₹|INR", text):
            currency = "INR"
        elif re.search(r"\$|USD", text):
            currency = "USD"
        elif re.search(r"€|EUR", text):
            currency = "EUR"
        elif re.search(r"£|GBP", text):
            currency = "GBP"

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency,
    }
