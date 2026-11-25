"""Explain a saved transaction using ERPNext's own counters and explicit document links."""

import frappe
from frappe import _
from frappe.utils import formatdate

from ai_lead_assistant.extensions.insight_access import readable_doc
from ai_lead_assistant.extensions.progress_signals import document_metrics, progress_findings
from ai_lead_assistant.framework.evidence_draft import draft_from_evidence, draft_options

# ERPNext can create a stock document from an invoice or an invoice from a stock document.
# The field lives on the item row of the document on the left.
ITEM_LINKS = {
	"Delivery Note": {"Sales Order": "against_sales_order", "Sales Invoice": "against_sales_invoice"},
	"Sales Invoice": {"Sales Order": "sales_order", "Delivery Note": "delivery_note"},
	"Purchase Receipt": {"Purchase Order": "purchase_order", "Purchase Invoice": "purchase_invoice"},
	"Purchase Invoice": {"Purchase Order": "purchase_order", "Purchase Receipt": "purchase_receipt"},
}
PER_TYPE = 3
MAX_SOURCE_ROWS = 500


def linked_names(doctype, filters):
	"""Ask the parent list API so user permissions and record sharing apply to the join."""
	try:
		return frappe.get_list(
			doctype,
			fields=["name", "modified"],
			filters=[*filters, [doctype, "docstatus", "=", 1]],
			order_by=f"`tab{doctype}`.modified desc, `tab{doctype}`.name asc",
			distinct=True,
			limit_page_length=PER_TYPE,
		)
	except frappe.PermissionError:
		return []


def source_links(doc):
	current = doc.doctype
	rows = doc.get("items") or []
	# A linked record can be referenced by several rows or from both directions.
	candidates = {}
	for target, field in ITEM_LINKS.get(current, {}).items():
		names = {row.get(field) for row in rows[:MAX_SOURCE_ROWS] if row.get(field)}
		if names:
			for match in linked_names(target, [[target, "name", "in", list(names)]]):
				candidates[(target, match.name)] = None

	for target, links in ITEM_LINKS.items():
		field = links.get(current)
		if not field or not frappe.has_permission(target, "read"):
			continue
		table = frappe.get_meta(target).get_field("items")
		child = frappe.get_meta(table.options)
		if table.permlevel and table.permlevel not in frappe.get_meta(target).get_permlevel_access("read"):
			continue
		if field not in child.get_permitted_fieldnames(parenttype=target):
			continue
		for match in linked_names(target, [[child.name, field, "=", doc.name]]):
			candidates.setdefault((target, match.name), field)

	if current in ITEM_LINKS:
		original = doc.get("return_against")
		if original:
			candidates[(current, original)] = None
		if "return_against" in frappe.get_meta(current).get_permitted_fieldnames():
			for match in linked_names(current, [[current, "return_against", "=", doc.name]]):
				candidates.setdefault((current, match.name), "return_against")

	counts = {}
	for (target, name), matched_field in candidates.items():
		if counts.get(target, 0) >= PER_TYPE:
			continue
		linked = readable_doc(target, name)
		if linked is None or linked.docstatus != 1:
			continue
		if matched_field == "return_against" and linked.get(matched_field) != doc.name:
			continue
		if matched_field and matched_field != "return_against":
			if not any(row.get(matched_field) == doc.name for row in linked.get("items") or []):
				continue
		counts[target] = counts.get(target, 0) + 1
		yield linked


def analyze(doc, query=""):
	findings = progress_findings(doc)
	current_count = len(findings)
	for linked in source_links(doc):
		status = linked.get("status") or _("Submitted")
		details = [_(status)]
		date = linked.get("posting_date") or linked.get("transaction_date")
		if date:
			details.append(formatdate(date))
		if linked.get("is_return") and status != "Return":
			details.append(_("Return"))
		if linked.get("update_stock"):
			details.append(_("Updates stock"))
		details.extend(document_metrics(linked))
		findings.append(
			{
				"title": _("Linked {0} · {1}").format(_(linked.doctype), linked.name),
				"detail": " · ".join(details),
				"doctype": linked.doctype,
				"name": linked.name,
			}
		)
	note = _(
		"Shows up to three directly linked, submitted records of each type that you can open. Each status applies to the whole document."
	)
	if len(findings) == current_count:
		note = _("The review found no submitted records you can open through the links it checked.")
	if doc.doctype in ("Sales Order", "Purchase Order") and current_count > 1:
		note += " " + _("Shows up to three outstanding order rows with a due date, earliest first.")
	if len(doc.get("items") or []) > MAX_SOURCE_ROWS:
		note += " " + _("Source links on this form were checked on the first {0} rows.").format(
			MAX_SOURCE_ROWS
		)
	return {
		"summary": _("{0} · {1}").format(_(doc.doctype), doc.name),
		"findings": findings,
		"note": note,
		**draft_options(findings),
	}


@frappe.whitelist(methods=["POST"])
def draft(doctype: str, document_name: str, version: str):
	return draft_from_evidence(
		"transaction_followup",
		doctype,
		document_name,
		version,
		instructions=(
			"Write a short internal transaction follow-up for the next colleague. Identify the next "
			"check supported by the current record. Keep quantity fulfillment, amount billed and "
			"payment balance distinct. Linked statuses apply to whole documents. The list is limited "
			"to visible, directly linked records. Never infer a missing payment, shipment, receipt "
			"or invoice from an absent link, or promise dates, approvals or payments."
		),
		unavailable=_("Configure OpenAI in AI Settings to draft a transaction follow-up."),
	)
