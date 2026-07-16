import re


EMAIL_REGEX = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)


def validate_fields(fields: dict) -> dict:
    validated = {}

    for field, value in fields.items():
        if not value:
            continue

        if field == "email_id":
            if not EMAIL_REGEX.match(value):
                continue

        if field in ("mobile_no", "phone"):
            value = _normalize_phone(value)

        validated[field] = value

    return remove_empty_fields(validated)


def _normalize_phone(phone: str) -> str:
    phone = re.sub(r"\s+", "", phone)
    return phone


def remove_empty_fields(fields: dict) -> dict:
    return {
        key: value
        for key, value in fields.items()
        if value not in ("", None)
    }