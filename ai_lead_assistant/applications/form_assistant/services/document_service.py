import frappe

logger = frappe.logger("ai_lead_assistant")

from ai_lead_assistant.applications.form_assistant.services import (
    llm_service,
    ocr_service,
    validation_service,
)


def extract_document(
    doctype: str,
    file_content: bytes,
) -> dict:
    """
    Extract ERPNext fields from a document.
    """

    ocr_text = ocr_service.extract_text(file_content)
    logger.info("OCR completed")
    print("=" * 60)
    print("OCR TEXT")
    print(ocr_text)
    print("=" * 60)

    fields = llm_service.extract_fields(
        doctype,
        ocr_text,
    )

    print("=" * 60)
    print("LLM OUTPUT")
    print(fields)
    print("=" * 60)

    logger.info(fields)

    fields = validation_service.validate_fields(fields)
    logger.info("Validation completed")

    print("=" * 60)
    print("VALIDATED OUTPUT")
    print(fields)
    print("=" * 60)

    return fields