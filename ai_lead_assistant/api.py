import frappe

from ai_lead_assistant.config import get_azure_document_intelligence_config, get_openai_config
from ai_lead_assistant.framework.assignments import require_form_feature
from ai_lead_assistant.services import document_service, file_service


@frappe.whitelist(methods=["POST"])
def process_document(file_url, doctype, document_name=None):

    require_form_feature("form_assistant", doctype, document_name)
    azure = get_azure_document_intelligence_config()
    if not (azure["endpoint"] and azure["api_key"] and get_openai_config()["api_key"]):
        frappe.throw(frappe._("Set up Azure Document Intelligence and OpenAI in AI Settings to use document extraction."))
    uploaded_file = file_service.get_uploaded_file(file_url)

    return document_service.extract_document(
        doctype=doctype,
        file_content=uploaded_file["content"],
        document_name=document_name,
    )
