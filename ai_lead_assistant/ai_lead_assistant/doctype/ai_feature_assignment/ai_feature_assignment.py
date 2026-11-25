import frappe
from frappe.model.document import Document


class AIFeatureAssignment(Document):
    pass


def on_doctype_update():
    frappe.db.add_unique("AI Feature Assignment", ["feature", "target_type", "target"])
