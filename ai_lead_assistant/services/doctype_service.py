import frappe

from ai_lead_assistant.config import (
    AI_EXTRACTABLE_FIELDS,
    AI_EXTRACTABLE_CHILD_FIELDS,
)


SUPPORTED_FIELD_TYPES = {
    "Data",
    "Small Text",
    "Text",
    "Text Editor",
    "Link",
    "Select",
    "Phone",
    "Int",
    "Float",
    "Currency",
    "Date",
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
    Return parent fields that are suitable for AI extraction.
    """

    meta = frappe.get_meta(doctype)

    ai_fields = []

    allowed_fields = AI_EXTRACTABLE_FIELDS.get(doctype, set())

    for field in meta.fields:

        if field.fieldname in EXCLUDED_FIELDS:
            continue

        if field.fieldtype not in SUPPORTED_FIELD_TYPES:
            continue

        if field.read_only:
            continue

        if field.fieldname not in allowed_fields:
            continue

        ai_fields.append(
            {
                "fieldname": field.fieldname,
                "label": field.label,
                "fieldtype": field.fieldtype,
                "required": field.reqd,
            }
        )

    return ai_fields


def get_extractable_child_fields(doctype: str) -> dict:
    """
    Return configured extractable fields for child tables.
    """

    meta = frappe.get_meta(doctype)

    configured_tables = AI_EXTRACTABLE_CHILD_FIELDS.get(doctype, {})

    child_fields = {}

    for field in meta.fields:

        if field.fieldtype != "Table":
            continue

        if field.fieldname not in configured_tables:
            continue

        child_doctype = field.options

        child_meta = frappe.get_meta(child_doctype)

        allowed_fields = configured_tables[field.fieldname]

        fields = []

        for child_field in child_meta.fields:

            if child_field.fieldname in EXCLUDED_FIELDS:
                continue

            if child_field.fieldtype not in SUPPORTED_FIELD_TYPES:
                continue

            if child_field.read_only:
                continue

            if child_field.fieldname not in allowed_fields:
                continue

            fields.append(
                {
                    "fieldname": child_field.fieldname,
                    "label": child_field.label,
                    "fieldtype": child_field.fieldtype,
                    "required": child_field.reqd,
                }
            )

        child_fields[field.fieldname] = {
            "fieldname": field.fieldname,
            "label": field.label,
            "fieldtype": field.fieldtype,
            "child_doctype": child_doctype,
            "fields": fields,
        }

    return child_fields