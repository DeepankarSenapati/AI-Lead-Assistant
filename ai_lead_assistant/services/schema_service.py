from ai_lead_assistant.services.doctype_service import (
    get_extractable_fields,
    get_extractable_child_fields,
)


FIELD_TYPE_MAP = {
    "Data": "string",
    "Small Text": "string",
    "Text": "string",
    "Text Editor": "string",
    "Phone": "string",
    "Link": "string",
    "Select": "string",
    "Date": "string",
    "Int": "integer",
    "Float": "number",
    "Currency": "number",
}


def _build_field_schema(field: dict) -> dict:
    """
    Build a nullable JSON schema for an ERPNext field.
    """

    field_type = FIELD_TYPE_MAP.get(
        field["fieldtype"],
        "string",
    )

    return {
        "type": [field_type, "null"]
    }


def build_json_schema(doctype: str) -> dict:
    """
    Build an OpenAI JSON Schema dynamically from ERPNext metadata.
    """

    fields = get_extractable_fields(doctype)
    child_fields = get_extractable_child_fields(doctype)

    properties = {}
    required = []

    # Parent fields
    for field in fields:

        properties[field["fieldname"]] = _build_field_schema(field)

        required.append(field["fieldname"])

    # Child tables
    for table_name, table in child_fields.items():

        child_properties = {}
        child_required = []

        for field in table["fields"]:

            child_properties[field["fieldname"]] = _build_field_schema(
                field
            )

            child_required.append(field["fieldname"])

        properties[table_name] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": child_properties,
                "required": child_required,
                "additionalProperties": False,
            },
        }

        required.append(table_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }