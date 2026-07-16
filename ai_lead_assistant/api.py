import frappe

from ai_lead_assistant.services import document_service, file_service


@frappe.whitelist()
def process_document(file_url, doctype):

    uploaded_file = file_service.get_uploaded_file(file_url)

    return document_service.extract_document(
        doctype=doctype,
        file_content=uploaded_file["content"],
    )