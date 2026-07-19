from ai_lead_assistant.applications.form_assistant.services.doctype_service import get_extractable_fields


def build_extraction_prompt(
    doctype: str,
    ocr_text: str,
) -> str:

    fields = get_extractable_fields(doctype)

    field_list = "\n\n".join(
    (
        f'Field Name: {field["fieldname"]}\n'
        f'Label: {field["label"]}\n'
        f'Type: {field["fieldtype"]}'
        + (
            f'\nDescription: {field["description"]}'
            if field.get("description")
            else ""
        )
    )
    for field in fields
    )
    
    json_template = "{\n" + ",\n".join(
    f'  "{field["fieldname"]}": ""'
    for field in fields
    ) + "\n}"

    return f"""
You are an ERPNext AI assistant.

Extract information from the OCR text.

Return ONLY valid JSON.

The JSON MUST exactly match this schema:

{json_template}

Available ERPNext fields:

{field_list}

Rules:

- Return ONLY JSON.
- Do not add extra keys.
- Missing values should be empty strings.
- Never invent information.
- Preserve the original values.

OCR Text:

{ocr_text}
"""