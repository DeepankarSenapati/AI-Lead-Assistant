from ai_lead_assistant.services.doctype_service import get_extractable_fields


FIELD_TYPE_MAP = {
    "Data": "string",
    "Small Text": "string",
    "Text": "string",
    "Text Editor": "string",
    "Phone": "string",
    "Link": "string",
    "Select": "string",
}


def build_json_schema(doctype: str) -> dict:
    """
    Build an OpenAI JSON Schema dynamically from ERPNext metadata.
    """

    fields = get_extractable_fields(doctype)

    properties = {}

    required = []

    for field in fields:

        properties[field["fieldname"]] = {
            "type": FIELD_TYPE_MAP.get(field["fieldtype"], "string")
        }

        # OpenAI requires every property to be listed in `required`
        required.append(field["fieldname"])

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }