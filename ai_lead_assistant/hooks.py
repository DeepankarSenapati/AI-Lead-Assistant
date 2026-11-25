app_name = "ai_lead_assistant"
app_title = "AI Lead Assistant"
app_publisher = "Deepankar Senapati"
app_description = "AI-powered Lead automation for ERPNext using OCR and LLMs."
app_email = "deepankar066@gmail.com"
app_license = "mit"


app_include_js = ["ai_lead_assistant.bundle.js"]
boot_session = "ai_lead_assistant.framework.assignments.boot_session"

fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                [
                    "Lead-custom_id_document_",
                    "Purchase Receipt-custom_receipt_document"
                ]
            ]
        ]
    }
]
