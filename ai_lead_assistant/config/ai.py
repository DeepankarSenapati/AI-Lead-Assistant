import frappe


def _get_ai_settings():
    try:
        return frappe.get_single("AI Settings")
    except Exception:
        return None


def get_azure_document_intelligence_config():
    settings = _get_ai_settings()

    endpoint = None
    api_key = None

    if settings:
        endpoint = settings.get("azure_document_intelligence_endpoint")

        if settings.get("azure_document_intelligence_key"):
            api_key = settings.get_password(
                "azure_document_intelligence_key"
            )

    return {
        "endpoint": endpoint or frappe.conf.get(
            "azure_document_intelligence_endpoint"
        ),
        "api_key": api_key or frappe.conf.get(
            "azure_document_intelligence_key"
        ),
    }


def get_openai_config():
    settings = _get_ai_settings()

    api_key = None
    model = None

    if settings:
        if settings.get("openai_api_key"):
            api_key = settings.get_password("openai_api_key")

        model = settings.get("openai_model")

    return {
        "api_key": api_key or frappe.conf.get("openai_api_key"),
        "model": model or frappe.conf.get(
            "openai_model",
            "gpt-4.1-mini",
        ),
    }