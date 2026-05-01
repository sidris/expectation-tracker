import re
from datetime import date

TARGET_KEYWORDS = {
    "year_end_cpi": ["sene sonu enflasyon", "yıl sonu enflasyon", "yıl sonu tüfe", "year-end inflation"],
    "monthly_cpi": ["aylık tüfe", "aylık enflasyon", "monthly cpi"],
    "annual_cpi": ["yıllık tüfe", "yıllık enflasyon", "annual cpi"],
    "policy_rate": ["ppk", "politika faizi", "policy rate"],
    "year_end_policy_rate": ["sene sonu faiz", "yıl sonu faiz", "sene sonu ppk"],
}

def guess_target_type(text: str) -> str:
    t = (text or "").lower()
    for key, words in TARGET_KEYWORDS.items():
        if any(w in t for w in words):
            return key
    return "year_end_cpi"

def extract_numbers(text: str):
    vals = []
    for m in re.finditer(r"(?<!\d)(\d{1,3}(?:[\.,]\d{1,4})?)\s*(?:%|yüzde)?", text or ""):
        vals.append(float(m.group(1).replace(",", ".")))
    return vals

def parse_capture(text: str):
    return {
        "target_type_guess": guess_target_type(text),
        "values_guess": extract_numbers(text),
        "raw_text": text,
        "parse_date": str(date.today()),
        "warning": "Bu sadece yardımcı ön ayrıştırmadır; kaydetmeden önce kontrol edin."
    }
