from ai_lead_assistant.services.doctype_service import (
    get_extractable_fields,
    get_extractable_child_fields,
)


def build_extraction_prompt(
    doctype: str,
    ocr_text: str,
) -> str:

    fields = get_extractable_fields(doctype)
    child_fields = get_extractable_child_fields(doctype)

    parent_field_list = "\n\n".join(
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

    child_field_sections = []

    for table_name, table in child_fields.items():

        child_field_list = "\n\n".join(
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
            for field in table["fields"]
        )

        child_field_sections.append(
            f'Table Field: {table_name}\n'
            f'Label: {table["label"]}\n'
            f'Child DocType: {table["child_doctype"]}\n\n'
            f'Child Fields:\n\n{child_field_list}'
        )

    child_field_list = "\n\n".join(child_field_sections)

    json_template_parts = []

    for field in fields:
        field_type = field["fieldtype"]

        if field_type in ("Int", "Float", "Currency"):
            example_value = "null"
        else:
            example_value = '""'

        json_template_parts.append(
            f'  "{field["fieldname"]}": {example_value}'
        )

    for table_name, table in child_fields.items():

        child_template = "{\n" + ",\n".join(
            f'      "{field["fieldname"]}": '
            + (
                "null"
                if field["fieldtype"] in ("Int", "Float", "Currency")
                else '""'
            )
            for field in table["fields"]
        ) + "\n    }"

        json_template_parts.append(
            f'  "{table_name}": [\n'
            f'    {child_template}\n'
            f'  ]'
        )

    json_template = "{\n" + ",\n".join(json_template_parts) + "\n}"

    return f"""
You are an ERPNext AI assistant.

Extract information from the provided OCR text.

The document may contain both parent-level information and multiple line items.

Return ONLY valid JSON.

The JSON MUST exactly match the provided schema.

Expected JSON structure:

{json_template}

Parent ERPNext fields:

{parent_field_list}

Child table fields:

{child_field_list}

Rules:

- Return ONLY JSON.
- Do not add extra keys.
- Extract only information explicitly present in the OCR text.
- Never invent or guess information.
- Preserve the values from the original document.
- For child tables, create one object for each line item found in the document.
- Do not combine separate line items.
- Do not omit a line item that contains extractable information.
- Do not calculate derived ERPNext values.
- Quantity must be returned as a number.
- Rate must be returned as a number.
- If a value is not present, return null.
- Populate each ERPNext field only when the document contains information that clearly corresponds to that field.
- Do not map an invoice number, purchase order number, or other reference into supplier_delivery_note unless it clearly represents the supplier delivery note.

OCR Text:

{ocr_text}
"""