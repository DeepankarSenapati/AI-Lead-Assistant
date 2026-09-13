app_name = "ai_lead_assistant"
app_title = "AI Lead Assistant"
app_publisher = "Deepankar Senapati"
app_description = "AI-powered Lead automation for ERPNext using OCR and LLMs."
app_email = "deepankar066@gmail.com"
app_license = "mit"


doctype_js = {
    "Lead": "public/js/lead.js",
    "Purchase Receipt": "public/js/purchase_receipt.js",
}

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