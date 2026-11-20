import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# 10 or 12 digits, separator -, + or none (personnummer and samordningsnummer).
_PERSONNUMMER = re.compile(r"(?<!\d)(?:\d{2})?\d{6}[-+]?\d{4}(?!\d)")
# +46, 0046 or 0 prefix, then 7 to 9 digits with optional single spaces or hyphens.
_PHONE = re.compile(r"(?<![\d\w])(?:\+46|0046|0)[\s-]?\d(?:[\s-]?\d){6,8}(?!\d)")


def redact(text: str) -> str:
    text = _EMAIL.sub("[EMAIL]", text)
    text = _PERSONNUMMER.sub("[PERSONNUMMER]", text)
    return _PHONE.sub("[PHONE]", text)
