"""A read-only manufacturing example. Nothing here reads or writes a site's business records."""

from datetime import timedelta

import frappe

from ai_lead_assistant.dispatch.comparison import enrich
from ai_lead_assistant.dispatch.settlement import assess
from ai_lead_assistant.dispatch.signals import lines_for_order, progress_band, rank
from ai_lead_assistant.dispatch.stock import coverage

COMPANY = "Sample Works"
# Item, customer, warehouse, promised in days, ordered, already dispatched, stock on hand.
LINES = (
	("Valve housing", "Northline Pumps", "Assembly", 0, 100, 40, 35),
	("Seal kit", "Oakfield Service", "Parts", -2, 24, 18, 3),
	("Mounting bracket", "Cedar Industrial", "Assembly", 1, 50, 0, 60),
	("Drive coupling", "Harbor Machines", "Finished Goods", 1, 80, 64, 80),
	("Bearing sleeve", "Juniper Works", "Parts", 2, 120, 24, 42),
	("Service manifold", "Northline Pumps", "Finished Goods", 3, 12, 0, 12),
	("Retaining ring", "Harbor Machines", "Parts", 4, 240, 180, 120),
	("Impeller", "Cedar Industrial", "Finished Goods", 5, 40, 0, 15),
	("Pump casing", "Oakfield Service", "Assembly", 6, 25, 15, 25),
)


class SampleLine(frappe._dict):
	def precision(self, _field):
		return 2


def _order(index, day, due_in, qty, delivered):
	item, customer, warehouse, *_ = LINES[index % len(LINES)]
	name = f"SAMPLE-SO-{index+1001}"
	line = SampleLine(
		name=f"{name}-1",
		item_code=item,
		warehouse=warehouse,
		qty=qty,
		delivered_qty=delivered,
		delivery_date=day + timedelta(days=due_in),
		uom="units",
		stock_uom="units",
		conversion_factor=1,
		is_stock_item=1,
		delivered_by_supplier=0,
	)
	return frappe._dict(
		name=name,
		company=COMPANY,
		customer=customer,
		docstatus=1,
		status="To Deliver",
		skip_delivery_note=0,
		items=[line],
	), line


def sample_data(day):
	from ai_lead_assistant.dispatch.api import history_view

	rows, promises, observations = [], [], []
	for i, (_, _, _, due, ordered, delivered, on_hand) in enumerate(LINES):
		doc, line = _order(i, day, due, ordered, delivered)
		row = lines_for_order(doc, day)[0]
		row["stock"] = coverage(row, on_hand)
		rows.append(row)
		if due >= 0:
			# Illustrate the first observed progress each day after entering the seven-day horizon.
			age = 6 - due
			for elapsed in range(age + 1):
				when = day - timedelta(days=age - elapsed)
				done = min(delivered, round(delivered * elapsed / max(1, age - 2))) if age else delivered
				observations.append(
					dict(
						order=doc.name,
						line=line.name,
						company=COMPANY,
						days=due + age - elapsed,
						band=progress_band(ordered, done),
						observed_on=when.isoformat(),
						due_date=line.delivery_date.isoformat(),
						resolved_on=None,
						outcome="Pending",
						ordered=ordered,
						delivered=done,
						uom=line.uom,
					)
				)
			promises.append(
				frappe._dict(
					order_name=doc.name,
					item_code=line.item_code,
					due_date=line.delivery_date,
					outcome="Pending",
					resolved_at=None,
					outcome_note="",
				)
			)

	# Generate repeatable illustrative postings, then let the same settlement and comparison code judge them.
	for cohort in range(16):
		observed = day - timedelta(days=82 - 5 * cohort)
		for j in range(16):
			lead = (0, 1, 2, 3)[j % 4]
			already = 40 if j % 8 < 4 else 80
			doc, line = _order(100 + cohort * 16 + j, observed, lead, 100, already)
			due = line.delivery_date
			late = (j * 3 + cohort) % 11 < (7 if already == 40 else 3)
			posted = due + timedelta(days=int(late))
			snap = frappe._dict(
				order_name=doc.name,
				line_id=line.name,
				company=COMPANY,
				item_code=line.item_code,
				uom=line.uom,
				stock_uom=line.stock_uom,
				conversion_factor=1,
				ordered_qty=100,
				qty_precision=2,
				due_date=due,
			)
			preamble = dict(
				order_name=doc.name,
				item_code=line.item_code,
				stock_uom=line.stock_uom,
				docstatus=1,
				is_return=0,
			)
			moves = [
				frappe._dict(**preamble, posting_date=observed, stock_qty=already),
				frappe._dict(**preamble, posting_date=posted, stock_qty=100 - already),
			]
			line.delivered_qty = 100
			if j == 15 and cohort % 4 == 0:
				doc.status = "Closed"
			outcome, note = assess(snap, doc, line, moves)
			resolved = due + timedelta(days=2)
			promises.append(
				frappe._dict(
					order_name=doc.name,
					item_code=line.item_code,
					due_date=due,
					outcome=outcome,
					resolved_at=resolved,
					outcome_note=note,
				)
			)
			observations.append(
				dict(
					order=doc.name,
					line=line.name,
					company=COMPANY,
					item=line.item_code,
					days=lead,
					band=progress_band(100, already),
					observed_on=observed.isoformat(),
					resolved_on=resolved.isoformat(),
					outcome=outcome,
					due_date=due.isoformat(),
				)
			)
	rows.sort(key=rank)
	history = history_view(promises)
	history["comparison"] = enrich(rows, observations, day)
	return dict(
		enabled=True,
		accessible=True,
		sample=True,
		as_of=day.isoformat(),
		rows=rows,
		history=history,
		truncated=False,
	)
