app_name = "ai_lead_assistant"
app_title = "AI Lead Assistant"
app_publisher = "Deepankar Senapati"
app_description = "AI-powered Lead automation for ERPNext using OCR and LLMs."
app_email = "deepankar066@gmail.com"
app_license = "mit"



doctype_js = {
    "Lead": "public/js/lead.js"
}

fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "=", "Lead-custom_id_document_"]
        ]
    }
]