import frappe
from frappe import _


def get_uploaded_file(file_url: str) -> dict:
    if not file_url or not file_url.startswith(("/files/", "/private/files/")):
        frappe.throw(_("Please select an uploaded document."))
    for name in frappe.get_all("File", filters={"file_url": file_url, "is_folder": 0}, pluck="name"):
        doc = frappe.get_doc("File", name)
        if doc.has_permission("read"):
            content = doc.get_content()
            return {"file_name": doc.file_name, "content": content.encode() if isinstance(content, str) else content}
    frappe.throw(_("You cannot access this file."), frappe.PermissionError)
