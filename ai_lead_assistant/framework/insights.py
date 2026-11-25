import frappe
from frappe import _

from ai_lead_assistant.extensions import FEATURES
from ai_lead_assistant.framework.assignments import require_form_feature


@frappe.whitelist(methods=["POST"])
def run(feature: str, doctype: str, document_name: str | None = None, query: str = ""):
	definition = FEATURES.get(feature)
	if not definition or not definition.analyzer or not definition.supports(doctype):
		frappe.throw(_("Choose an available insight for this form."))
	require_form_feature(feature, doctype, document_name)
	if definition.needs_saved and not document_name:
		frappe.throw(_("Save this document before running the review."))
	if len(query) > 500:
		frappe.throw(_("Use a search of 500 characters or fewer."))
	if document_name:
		doc = frappe.get_doc(doctype, document_name)
		doc.check_permission("read")
		doc.apply_fieldlevel_read_permissions()
	else:
		# No unsaved form payload or client-supplied linked rows enter an analyzer.
		doc = frappe._dict(doctype=doctype)
	return frappe.get_attr(definition.analyzer)(doc, query.strip())
