"""Current warehouse stock as physical evidence for a visible Sales Order line."""

from collections import defaultdict

import frappe
from frappe.utils import flt


def coverage(row, actual_qty):
	# A Bin is in stock UOM. Keep the comparison in stock units to avoid rounding up a partial order unit.
	needed = flt(row["remaining"] * row["factor"], 9)
	short = flt(max(0, needed - max(0, actual_qty)), 9)
	return {"on_hand": actual_qty, "needed": needed, "short": short, "uom": row["stock_uom"]}


def add_stock(rows):
	if not rows or not frappe.has_permission("Bin", "read"):
		return
	meta = frappe.get_meta("Bin")
	levels = set(meta.get_permlevel_access("read")) | {0}
	fields = ("item_code", "warehouse", "stock_uom", "actual_qty")
	if any(meta.get_field(f).permlevel not in levels for f in fields):
		return
	items_by_warehouse = defaultdict(set)
	for row in rows:
		if row["warehouse"]:
			items_by_warehouse[row["warehouse"]].add(row["item"])
	bins = {}
	for warehouse, items in items_by_warehouse.items():
		for record in frappe.get_list(
			"Bin",
			filters={"warehouse": warehouse, "item_code": ["in", sorted(items)]},
			fields=["name", *fields],
			limit_page_length=0,
		):
			# A site may also restrict individual stock records through a document permission hook.
			if record.actual_qty is not None and frappe.has_permission("Bin", "read", doc=record.name):
				bins[(record.warehouse, record.item_code, record.stock_uom)] = record.actual_qty
	for row in rows:
		qty = bins.get((row["warehouse"], row["item"], row["stock_uom"]))
		if qty is not None:
			row["stock"] = coverage(row, qty)
