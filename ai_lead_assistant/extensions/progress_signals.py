"""Follow-up findings from a field-permission-filtered ERPNext transaction."""

from frappe import _
from frappe.utils import flt, fmt_money, formatdate, getdate


def finding(doc, title, detail, level="info"):
	return {"title": title, "detail": detail, "level": level, "doctype": doc.doctype, "name": doc.name}


def progress_findings(doc):
	if doc.docstatus == 0:
		return [
			finding(
				doc, _("Saved draft"), _("Review the draft before treating its figures as posted progress.")
			)
		]
	if doc.docstatus == 2:
		return [
			finding(
				doc,
				_("Cancelled"),
				_("This transaction is cancelled. Check any amended document separately."),
			)
		]
	if doc.doctype in ("Sales Order", "Purchase Order"):
		return _order(doc)
	if doc.doctype in ("Delivery Note", "Purchase Receipt"):
		return _stock_document(doc)
	return _invoice(doc)


def _number(value, precision):
	text = f"{value:.{precision}f}"
	return text.rstrip("0").rstrip(".") if "." in text else text


def document_metrics(doc):
	"""All figures describe this whole record, including when it is a linked source."""
	parts = []
	if doc.doctype in ("Sales Order", "Purchase Order"):
		sales = doc.doctype == "Sales Order"
		quantity = doc.get("per_delivered" if sales else "per_received")
		if quantity is not None:
			msg = _("{0}% delivered by quantity.") if sales else _("{0}% received by quantity.")
			parts.append(msg.format(_number(quantity, 6)))
	billed = doc.get("per_billed")
	if billed is not None and doc.doctype not in ("Sales Invoice", "Purchase Invoice"):
		parts.append(_("{0}% billed by amount.").format(_number(billed, 6)))
	currency, amount = doc.get("party_account_currency"), doc.get("outstanding_amount")
	if currency and amount is not None and doc.doctype in ("Sales Invoice", "Purchase Invoice"):
		parts.append(
			_("Outstanding balance on this invoice: {0} {1}.").format(
				currency, fmt_money(amount, precision=doc.precision("outstanding_amount"))
			)
		)
	return parts


def _order(doc):
	sales = doc.doctype == "Sales Order"
	status = doc.get("status")
	quantity = doc.get("per_delivered" if sales else "per_received")
	billed = doc.get("per_billed")
	parts = document_metrics(doc)
	active = status in ("To Deliver and Bill", "To Deliver", "To Receive and Bill", "To Receive", "To Bill")
	skip = doc.get("skip_delivery_note") if sales else 0
	if status == "On Hold":
		parts.append(_("Check why the order is on hold before following up."))
	elif status == "Closed":
		parts.append(_("ERPNext has closed the remaining work on this order."))
	elif status == "Completed":
		parts.append(_("ERPNext marks the order complete. Payments are tracked on invoices."))
	elif skip:
		parts.append(_("This order skips the Delivery Note."))
	if (
		status in ("To Deliver and Bill", "To Receive and Bill", "To Bill")
		and billed is not None
		and billed < 100
	):
		parts.append(_("Check the unbilled portion against the agreed billing terms."))
	facts = [
		finding(
			doc,
			_(status) if status else _("Order progress"),
			" ".join(parts) or _("Open the order for its recorded status."),
		)
	]
	if active and status != "To Bill" and skip == 0 and quantity is not None and quantity < 100:
		facts.extend(_due_lines(doc, sales))
	return facts


def _due_lines(doc, sales):
	done_field, date_field = (
		("delivered_qty", "delivery_date") if sales else ("received_qty", "schedule_date")
	)
	rows = []
	for row in doc.get("items") or []:
		qty, done = row.get("qty"), row.get(done_field)
		if row.get("delivered_by_supplier") != 0 or qty is None or done is None:
			continue
		if not (row.get("item_code") and row.get("uom") and row.get(date_field)):
			continue
		# ERPNext maintains the fulfilled quantity in the order row's UOM.
		pending = flt(qty - done, row.precision("qty"))
		if pending > 0:
			rows.append((getdate(row.get(date_field)), row.idx, row, pending))
	out = []
	today = getdate()
	for due, idx, row, pending in sorted(rows, key=lambda entry: entry[:2])[:3]:
		if due < today:
			title = _("Overdue since {0}").format(formatdate(due))
		elif due == today:
			title = _("Due today")
		else:
			title = _("Due {0}").format(formatdate(due))
		line = (
			_("Row {0} · {1} · {2} {3} still to deliver.")
			if sales
			else _("Row {0} · {1} · {2} {3} still to receive.")
		)
		out.append(
			finding(
				doc,
				title,
				line.format(idx, row.item_code, _number(pending, row.precision("qty")), row.uom),
				"warning" if due < today else "info",
			)
		)
	return out


def _stock_document(doc):
	status, billed = doc.get("status"), doc.get("per_billed")
	parts = document_metrics(doc)
	if doc.get("is_return") or status == "Return":
		parts.append(_("This is a stock return. Check the original transaction for its effect."))
	elif status == "Return Issued":
		parts.append(_("A return was issued against this document. Review the original and return together."))
	elif status == "Closed":
		parts.append(_("This stock document is closed."))
	elif status in ("To Bill", "Partly Billed", "Partially Billed") and billed is not None and billed < 100:
		parts.append(_("Compare the unbilled portion with the invoicing terms."))
	return [
		finding(
			doc,
			_(status) if status else _("Stock document"),
			" ".join(parts) or _("Open the stock document for its saved progress."),
		)
	]


def _invoice(doc):
	status, amount = doc.get("status"), doc.get("outstanding_amount")
	parts = document_metrics(doc)
	if doc.get("is_return") or status == "Return":
		parts.append(_("This is a credit or debit note. Check its allocation against the original invoice."))
	elif status in ("Credit Note Issued", "Debit Note Issued", "Internal Transfer"):
		parts.append(_("Check the linked records for the accounting treatment."))
	elif doc.get("on_hold"):
		parts.append(_("Payment is on hold. Review the hold details on this invoice."))
	elif status and status.startswith("Overdue"):
		parts.append(
			_("ERPNext flags this invoice as overdue. Check its payment terms for the portion currently due.")
		)
	elif status == "Paid":
		parts.append(_("ERPNext marks this invoice paid."))
	elif (
		amount is not None
		and amount > 0
		and status in ("Unpaid", "Partly Paid", "Unpaid and Discounted", "Partly Paid and Discounted")
	):
		parts.append(_("Check the payment terms for the next installment."))
	if doc.get("due_date"):
		parts.append(_("Invoice due date: {0}.").format(formatdate(doc.due_date)))
	invoice = finding(
		doc,
		_(status) if status else _("Invoice progress"),
		" ".join(parts) or _("Open the invoice for its saved payment status."),
		"warning" if doc.get("on_hold") or (status or "").startswith("Overdue") else "info",
	)
	out = [invoice]
	if doc.get("update_stock"):
		out.append(
			finding(doc, _("Update Stock is enabled"), _("This invoice records stock movement directly."))
		)
	return out
