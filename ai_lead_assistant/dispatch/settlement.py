"""Score the frozen quantity and date against submitted outbound postings in stock units."""

from math import isclose

from frappe.utils import flt, getdate

from ai_lead_assistant.dispatch.signals import format_qty


def assess(snapshot, order, row, movements):
	if not order or not row:
		return "Excluded", "The order or its original line is no longer available."
	if order.docstatus != 1 or order.status in ("Closed", "On Hold", "Stopped") or order.skip_delivery_note:
		return "Excluded", "The order was cancelled, closed, paused or set to skip dispatch."
	if order.company != snapshot.company or not row.is_stock_item or row.delivered_by_supplier:
		return "Excluded", "The company or fulfillment method changed."
	if any(row.get(k) != snapshot.get(k) for k in ("item_code", "stock_uom", "uom")):
		return "Excluded", "The item or its unit of measure changed."
	factor = snapshot.conversion_factor
	precision = snapshot.qty_precision
	if not factor or factor <= 0 or not isclose(row.conversion_factor or 0, factor, rel_tol=1e-9):
		return "Excluded", "The conversion between the order and stock units changed."
	if flt(row.qty - snapshot.ordered_qty, precision):
		return "Excluded", "The ordered quantity changed after the promise was first observed."

	total = by_deadline = 0.0
	for move in movements:
		if move.docstatus != 1:
			continue
		if move.is_return or move.stock_qty is None or move.stock_qty < 0:
			return "Excluded", "A return or reversal makes the original outbound quantity ambiguous."
		if (move.order_name, move.item_code, move.stock_uom) != (
			snapshot.order_name,
			snapshot.item_code,
			snapshot.stock_uom,
		) or not move.posting_date:
			return "Excluded", "A linked posting has inconsistent order, item, stock unit or date."
		total += move.stock_qty
		if getdate(move.posting_date) <= getdate(snapshot.due_date):
			by_deadline += move.stock_qty
	if row.delivered_qty is None or flt(total / factor - row.delivered_qty, precision):
		return "Excluded", "The submitted dispatch postings do not reconcile with the order."
	shipped = flt(by_deadline / factor, precision)
	outcome = "On time" if flt(snapshot.ordered_qty - shipped, precision) <= 0 else "Missed"
	return (
		outcome,
		f"{format_qty(shipped, precision)} of {format_qty(snapshot.ordered_qty, precision)} {snapshot.uom} posted as dispatched by the frozen promise date.",
	)
