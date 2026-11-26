"""Desk read model for the live dispatch queue and isolated sample."""

from collections import Counter
from datetime import timedelta
from functools import lru_cache

import frappe
from frappe import _
from frappe.utils import cint, getdate

from ai_lead_assistant.dispatch.comparison import enrich
from ai_lead_assistant.dispatch.history import CHECKPOINT, HISTORY_DAYS, is_enabled, recent_promises
from ai_lead_assistant.dispatch.signals import candidate_filters, format_qty, lines_for_order, rank
from ai_lead_assistant.dispatch.stock import add_stock
from ai_lead_assistant.extensions.insight_access import readable_doc

PAGE_SIZE = 200
DISPLAY_LIMIT = 300
PARENT_LIMIT = 500


def can_read_inputs():
	if not frappe.has_permission("Sales Order", "read"):
		return False
	# Filters and derived history must respect restricted fields just as current-row values do.
	meta = frappe.get_meta("Sales Order")
	levels = set(meta.get_permlevel_access("read")) | {0}
	tables = (
		(meta, ("company", "items", "status", "skip_delivery_note")),
		(
			frappe.get_meta("Sales Order Item"),
			(
				"item_code",
				"uom",
				"stock_uom",
				"conversion_factor",
				"is_stock_item",
				"delivered_by_supplier",
				"qty",
				"delivered_qty",
				"delivery_date",
			),
		),
	)
	return all((doc.get_field(field).permlevel or 0) in levels for doc, fields in tables for field in fields)


def _live(day, read_order):
	names = frappe.get_list(
		"Sales Order",
		filters=candidate_filters(day, overdue=True),
		fields=["name"],
		group_by="`tabSales Order`.name",
		order_by="min(`tabSales Order Item`.delivery_date) asc, `tabSales Order`.name asc",
		limit_page_length=PARENT_LIMIT + 1,
	)
	rows = []
	for name in names[:PARENT_LIMIT]:
		doc = read_order(name.name)
		if doc:
			rows.extend(lines_for_order(doc, day))
	rows.sort(key=rank)
	return rows[:DISPLAY_LIMIT], len(names) > PARENT_LIMIT or len(rows) > DISPLAY_LIMIT


def _visible_history(day, read_order):
	candidates = recent_promises(day)
	order_names = sorted({s.order_name for s in candidates})
	companies = {}
	for start in range(0, len(order_names), PAGE_SIZE):
		names = frappe.get_list(
			"Sales Order",
			filters={"name": ["in", order_names[start : start + PAGE_SIZE]]},
			pluck="name",
			limit_page_length=0,
		)
		for name in names:
			if order := read_order(name):
				companies[name] = order.get("company")
	visible = [s for s in candidates if s.company and companies.get(s.order_name) == s.company]
	checkpoints = []
	for start in range(0, len(visible), PAGE_SIZE):
		by_name = {s.name: s for s in visible[start : start + PAGE_SIZE]}
		points = frappe.get_all(
			CHECKPOINT,
			filters={
				"parent": ["in", list(by_name)],
				"parenttype": "AI Dispatch Promise",
				"parentfield": "checkpoints",
			},
			fields=[
				"parent",
				"observed_on",
				"captured_at",
				"days_left",
				"progress_band",
				"ordered_qty",
				"delivered_qty",
				"uom",
			],
		)
		for p in points:
			s = by_name[p.parent]
			checkpoints.append(
				dict(
					order=s.order_name,
					line=s.line_id,
					company=s.company,
					item=s.item_code,
					days=p.days_left,
					band=p.progress_band,
					ordered=p.ordered_qty,
					delivered=p.delivered_qty,
					uom=p.uom,
					captured_at=str(p.captured_at),
					observed_on=str(p.observed_on),
					due_date=str(s.due_date),
					resolved_on=str(getdate(s.resolved_at)) if s.resolved_at else None,
					outcome=s.outcome,
				)
			)
	return visible, checkpoints


def history_view(promises):
	counts = Counter(s.outcome for s in promises)
	settled = sorted(
		(s for s in promises if s.resolved_at), key=lambda s: (str(s.resolved_at), s.order_name), reverse=True
	)
	return dict(
		observed=len(promises),
		on_time=counts["On time"],
		missed=counts["Missed"],
		excluded=counts["Excluded"],
		awaiting=counts["Pending"],
		latest=[
			dict(
				order=s.order_name,
				item=s.item_code,
				due_date=str(s.due_date),
				outcome=s.outcome,
				reason=s.outcome_note,
			)
			for s in settled[:20]
		],
	)


@frappe.whitelist(methods=["GET", "POST"])
def get_watchlist(sample: int = 0):
	if frappe.session.user == "Guest":
		frappe.throw(_("Sign in to open the dispatch watchlist."), frappe.PermissionError)
	day = getdate()
	if cint(sample):
		from ai_lead_assistant.dispatch.sample import sample_data

		return sample_data(day)
	active, accessible = is_enabled(), can_read_inputs()
	rows, promises, observations, truncated = [], [], [], False
	if active and accessible:

		@lru_cache(maxsize=PARENT_LIMIT)
		def read_order(name):
			return readable_doc("Sales Order", name)

		rows, truncated = _live(day, read_order)
		add_stock(rows)
		promises, observations = _visible_history(day, read_order)
	history = history_view(
		[s for s in promises if getdate(s.due_date) >= day - timedelta(days=HISTORY_DAYS - 1)]
	)
	history["comparison"] = enrich(rows, observations, day)
	return dict(
		enabled=active,
		accessible=accessible,
		as_of=day.isoformat(),
		sample=False,
		rows=rows,
		history=history,
		truncated=truncated,
	)


def analyze(doc, query=""):
	if not can_read_inputs():
		frappe.throw(_("Read access to dispatch dates and quantities is required."), frappe.PermissionError)
	rows = sorted(lines_for_order(doc, getdate()), key=rank)
	selection = rows[:20]
	add_stock(selection)
	findings = []
	for r in selection:
		detail = f"{r['reason']} Promised {r['due_date']}."
		if (stock := r.get("stock")) and stock["short"]:
			detail += f" Current stock at {r['warehouse']} falls short by {format_qty(stock['short'], 9)} {stock['uom']}."
		findings.append(
			dict(
				title=f"{r['item']} · {r['priority']}",
				detail=detail,
				doctype="Sales Order",
				name=doc.name,
				level="warning" if r["days"] <= 0 else "info",
			)
		)
	return dict(
		summary=_("{0} open lines in the dispatch window").format(len(rows)),
		findings=findings,
		note=_(
			"Includes warehouse-dispatched stock items due today or in the next six days, plus the last 30 days overdue. Shows up to 20 lines on this form."
		),
	)
