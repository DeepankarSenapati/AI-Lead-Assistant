import frappe


def get_configuration(doctype: str):
    config = frappe.get_all(
        "AI Form Configuration",
        filters={
            "enabled": 1,
            "target_doctype": doctype,
        },
        fields=["name", "document_field"],
        limit=1,
    )

    if not config:
        return None

    return frappe.get_doc("AI Form Configuration", config[0].name)