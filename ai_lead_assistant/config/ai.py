import frappe


def get_azure_document_intelligence_config():
    return {
        "endpoint": frappe.conf.get("azure_document_intelligence_endpoint"),
        "api_key": frappe.conf.get("azure_document_intelligence_key"),
    }


def get_openai_config():
    return {
        "api_key": frappe.conf.get("openai_api_key"),
        "model": frappe.conf.get("openai_model", "gpt-4.1-mini"),
    }