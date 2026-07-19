import frappe
from ai_lead_assistant.applications.form_assistant.config import (
    AI_EXTRACTABLE_FIELDS,
)
SUPPORTED_FIELD_TYPES = {
    "Data",
    "Small Text",
    "Text",
    "Text Editor",
    "Link",
    "Select",
    "Phone",
}


EXCLUDED_FIELDS = {
    "name",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "docstatus",
    "idx",
    "parent",
    "parentfield",
    "parenttype",
    "_assign",
    "_comments",
    "_liked_by",
    "_seen",
}


def get_extractable_fields(doctype: str) -> list[dict]:
    """
    Return fields that are suitable for AI extraction.
    """

    meta = frappe.get_meta(doctype)

    ai_fields = []

    for field in meta.fields:

        if field.fieldname in EXCLUDED_FIELDS:
            continue

        if field.fieldtype not in SUPPORTED_FIELD_TYPES:
            continue

        if field.read_only:
            continue

        # If configured, use only configured fields.
        # Otherwise, allow all supported fields.
        allowed_fields = AI_EXTRACTABLE_FIELDS.get(doctype)

        if allowed_fields is not None and field.fieldname not in allowed_fields:
            continue

        ai_fields.append(
            {
                "fieldname": field.fieldname,
                "label": field.label,
                "fieldtype": field.fieldtype,
                "required": field.reqd,
            }
        )

    print("=" * 60)
    print("DOCTYPE:", doctype)
    print("EXTRACTABLE FIELDS:")
    print(ai_fields)
    print("=" * 60)

    return ai_fields