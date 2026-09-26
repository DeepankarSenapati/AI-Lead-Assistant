import frappe

logger = frappe.logger("ai_lead_assistant")

from ai_lead_assistant.services import (
    address_service,
    llm_service,
    ocr_service,
    validation_service,
)


def extract_document(
    doctype: str,
    file_content: bytes,
    document_name: str | None = None,
) -> dict:
    """
    Extract ERPNext fields from a document.
    """

    ocr_text = ocr_service.extract_text(file_content)
    logger.info("OCR completed")

    fields = llm_service.extract_fields(
        doctype,
        ocr_text,
    )
    logger.info(fields)

    fields = validation_service.validate_fields(fields)
    logger.info("Validation completed")

    if doctype == "Lead" and document_name:
        address_data = fields.pop("address", None)

        if address_data:
            address_service.create_address_for_lead(
                lead_name=document_name,
                address_data=address_data,
            )

    return fields
