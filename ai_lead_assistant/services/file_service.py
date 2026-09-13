from frappe.utils.file_manager import get_file
import frappe


def get_uploaded_file(file_url: str) -> dict:
    """
    Returns the uploaded file as raw bytes.
    """

    if not file_url:
        frappe.throw("Please upload a document first.")

    file_name, content = get_file(file_url)

    return {
        "file_name": file_name,
        "content": content,
    }