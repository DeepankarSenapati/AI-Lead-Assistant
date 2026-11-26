"""Prospective observations. Only the site scheduler writes these private tables."""

import hashlib
import json
from collections import defaultdict
from datetime import timedelta

import frappe
from frappe.utils import flt, getdate, now_datetime

from ai_lead_assistant.dispatch.settlement import assess
from ai_lead_assistant.dispatch.signals import FEATURE, WINDOW, candidate_filters, lines_for_order
from ai_lead_assistant.framework.assignments import enabled, rules_for

PROMISE = "AI Dispatch Promise"
CHECKPOINT = "AI Dispatch Checkpoint"
BATCH = 100
HISTORY_DAYS = 90
POSTING_GRACE_DAYS = 1


def is_enabled():
	return enabled(FEATURE, "Selling", "Sales Order", rules_for("Selling", "Sales Order"))


def _key(*parts):
	return hashlib.sha256(json.dumps(parts, default=str).encode()).hexdigest()


def capture_line(line, stamp):
	"""Deterministic primary keys keep the first sighting and each day's first checkpoint."""
	day = getdate(stamp)
	name = _key(line["order"], line["line"], line["due_date"])
	frappe.get_doc(
		dict(
			doctype=PROMISE,
			name=name,
			order_name=line["order"],
			line_id=line["line"],
			company=line["company"],
			item_code=line["item"],
			uom=line["uom"],
			stock_uom=line["stock_uom"],
			conversion_factor=line["factor"],
			qty_precision=line["precision"],
			first_seen=stamp,
			due_date=line["due_date"],
			ordered_qty=line["qty"],
			outcome="Pending",
		)
	).db_insert(ignore_if_duplicate=True)
	frappe.get_doc(
		dict(
			doctype=CHECKPOINT,
			name=_key(name, day),
			parent=name,
			parenttype=PROMISE,
			parentfield="checkpoints",
			idx=WINDOW - line["days"],
			observed_on=day,
			captured_at=stamp,
			days_left=line["days"],
			ordered_qty=line["qty"],
			delivered_qty=line["delivered"],
			uom=line["uom"],
			progress_band=line["band"],
		)
	).db_insert(ignore_if_duplicate=True)


def movement_map(line_ids):
	"""Use the same order-row identifiers and converted quantities as ERPNext's status updater."""
	result = defaultdict(list)
	for kind, order_field in (("Delivery Note", "against_sales_order"), ("Sales Invoice", "sales_order")):
		parent = frappe.qb.DocType(kind)
		item = frappe.qb.DocType(f"{kind} Item")
		query = (
			frappe.qb.from_(item)
			.join(parent)
			.on(parent.name == item.parent)
			.select(
				item.so_detail,
				item[order_field].as_("order_name"),
				item.item_code,
				item.stock_uom,
				(item.qty * item.conversion_factor).as_("stock_qty"),
				parent.posting_date,
				parent.is_return,
				parent.docstatus,
			)
			.where(
				(item.so_detail.isin(line_ids))
				& (parent.docstatus == 1)
				& (item.parenttype == kind)
				& (item.parentfield == "items")
			)
		)
		if kind == "Sales Invoice":
			query = query.where(parent.update_stock == 1)
		for movement in query.run(as_dict=True):
			result[movement.so_detail].append(movement)
	return result


def settle_batch(names, stamp):
	snapshots = frappe.get_all(PROMISE, filters={"name": ["in", names], "outcome": "Pending"}, fields=["*"])
	if not snapshots:
		return
	moves = movement_map({s.line_id for s in snapshots})
	observed = defaultdict(list)
	for point in frappe.get_all(
		CHECKPOINT,
		filters={"parent": ["in", names], "parenttype": PROMISE, "parentfield": "checkpoints"},
		fields=["parent", "ordered_qty", "uom"],
	):
		observed[point.parent].append(point)
	orders = {}
	for snap in snapshots:
		if getdate(snap.due_date) >= getdate(stamp) - timedelta(days=POSTING_GRACE_DAYS):
			continue
		if snap.order_name not in orders:
			try:
				doc = frappe.get_doc("Sales Order", snap.order_name)
			except frappe.DoesNotExistError:
				doc = None
			orders[snap.order_name] = (doc, {r.name: r for r in doc.items} if doc else {})
		order, rows = orders[snap.order_name]
		if any(
			p.uom != snap.uom or flt(p.ordered_qty - snap.ordered_qty, snap.qty_precision)
			for p in observed[snap.name]
		):
			outcome, note = (
				"Excluded",
				"A daily observation recorded a change in the promised quantity or unit.",
			)
		else:
			outcome, note = assess(snap, order, rows.get(snap.line_id), moves[snap.line_id])
		# Two workers may observe the same pending promise. Only its first assessment wins.
		table = frappe.qb.DocType(PROMISE)
		(
			frappe.qb.update(table)
			.set(table.outcome, outcome)
			.set(table.outcome_note, note)
			.set(table.resolved_at, stamp)
			.where((table.name == snap.name) & (table.outcome == "Pending"))
		).run()


def collect():
	"""Hourly retries cover orders entering the seven-day horizon during the day. Never backfill inputs."""
	if not is_enabled():
		return
	day = getdate()
	cursor = ""
	while is_enabled():
		names = frappe.get_all(
			"Sales Order",
			filters=[*candidate_filters(day, overdue=False), ["Sales Order", "name", ">", cursor]],
			fields=["name"],
			distinct=True,
			order_by="`tabSales Order`.name asc",
			limit_page_length=BATCH,
		)
		if not names:
			break
		for rec in names:
			try:
				doc = frappe.get_doc("Sales Order", rec.name)
			except frappe.DoesNotExistError:
				continue
			stamp = now_datetime()
			if getdate(stamp) != day:
				frappe.db.commit()
				return
			for line in lines_for_order(doc, day, overdue=False):
				capture_line(line, stamp)
		frappe.db.commit()
		cursor = names[-1].name
	while is_enabled():
		names = frappe.get_all(
			PROMISE,
			filters={"due_date": ["<", day - timedelta(days=POSTING_GRACE_DAYS)], "outcome": "Pending"},
			pluck="name",
			order_by="due_date asc, name asc",
			limit_page_length=BATCH,
		)
		if not names:
			break
		settle_batch(names, now_datetime())
		frappe.db.commit()


def recent_promises(day):
	"""Private candidate list; callers must scope parent and field access before returning aggregates."""
	return frappe.get_all(
		PROMISE,
		filters={
			"due_date": [
				"between",
				[day - timedelta(days=HISTORY_DAYS + 30), day + timedelta(days=WINDOW - 1)],
			]
		},
		fields=[
			"name",
			"order_name",
			"line_id",
			"item_code",
			"company",
			"due_date",
			"first_seen",
			"outcome",
			"resolved_at",
			"outcome_note",
		],
		order_by="due_date desc, name asc",
	)
