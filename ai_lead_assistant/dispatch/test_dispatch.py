from datetime import datetime, time, timedelta
from unittest.mock import patch

import frappe
from frappe.utils import getdate

from ai_lead_assistant.dispatch.api import get_watchlist
from ai_lead_assistant.dispatch.history import (
	CHECKPOINT,
	PROMISE,
	capture_line,
	collect,
	movement_map,
	settle_batch,
)
from ai_lead_assistant.dispatch.signals import FEATURE, lines_for_order
from ai_lead_assistant.dispatch.stock import coverage
from ai_lead_assistant.extensions.test_insights import InsightTestCase
from ai_lead_assistant.framework.assignments import get_form_features, set_assignment
from ai_lead_assistant.framework.insights import run


class TestDispatch(InsightTestCase):
	def setUp(self):
		super().setUp()
		self.day = getdate()
		self.assign(FEATURE, "Sales Order")

	def order(self, suffix, offset=2, **override):
		line = dict(
			item_code="DW-VALVE",
			qty=10,
			delivered_qty=2,
			conversion_factor=2,
			stock_uom="Nos",
			uom="Pair",
			is_stock_item=1,
			delivered_by_supplier=0,
			delivery_date=self.day + timedelta(days=offset),
		)
		line.update(override)
		return self.record(
			"Sales Order",
			suffix,
			docstatus=1,
			status="To Deliver",
			company=self.company,
			skip_delivery_note=0,
			items=[line],
		)

	def freeze(self, doc, day=None):
		day = day or self.day
		rows = lines_for_order(doc, day, overdue=False)
		self.assertEqual(len(rows), 1)
		capture_line(rows[0], datetime.combine(day, time(8, 0)))
		return frappe.db.get_value(PROMISE, {"order_name": doc.name, "due_date": rows[0]["due_date"]}, "name")

	def test_horizon_and_field_rules(self):
		included = [self.order("-due", 0), self.order("-end", 6), self.order("-prior", -30)]
		excluded = [
			self.order("-far", 7),
			self.order("-old", -31),
			self.order("-service", is_stock_item=0),
			self.order("-drop", delivered_by_supplier=1),
			self.order("-full", delivered_qty=10),
		]
		view = get_watchlist()
		names = {r["order"] for r in view["rows"]}
		for doc in included:
			self.assertIn(doc.name, names)
		for doc in excluded:
			self.assertNotIn(doc.name, names)
		result = run(FEATURE, "Sales Order", included[0].name)
		self.assertIn("8 Pair", str(result))
		with self.assertRaises(frappe.ValidationError):
			set_assignment(FEATURE, "DocType", "Delivery Note", "on")
		set_assignment(FEATURE, "DocType", "Sales Order", "off")
		self.assertFalse(get_watchlist()["enabled"])
		with self.assertRaises(frappe.PermissionError):
			run(FEATURE, "Sales Order", included[0].name)

	def test_capture_daily_first_values_and_frozen_promises(self):
		doc = self.order("-frozen")
		name = self.freeze(doc)
		self.freeze(doc)
		self.assertEqual(frappe.db.count(CHECKPOINT, {"parent": name}), 1)
		view = next(r for r in get_watchlist()["rows"] if r["order"] == doc.name)
		self.assertEqual(view["trend"], [{"date": str(self.day), "delivered": 2}])
		doc.items[0].delivered_qty = 5
		self.freeze(doc)
		self.assertEqual(frappe.db.get_value(CHECKPOINT, {"parent": name}, "delivered_qty"), 2)
		next_day = self.day + timedelta(days=1)
		self.freeze(doc, next_day)
		self.assertEqual(frappe.db.count(CHECKPOINT, {"parent": name}), 2)
		old_due = doc.items[0].delivery_date
		doc.items[0].delivery_date += timedelta(days=2)
		other = self.freeze(doc, next_day)
		self.assertNotEqual(name, other)
		self.assertEqual(frappe.db.get_value(PROMISE, name, "due_date"), old_due)

	def test_scheduler_retries_are_idempotent(self):
		doc = self.order("-cron")
		with patch.object(frappe.db, "commit"):
			collect()
			collect()
		name = frappe.db.get_value(PROMISE, {"order_name": doc.name}, "name")
		self.assertTrue(name)
		self.assertEqual(frappe.db.count(CHECKPOINT, {"parent": name}), 1)

	def test_observed_quantity_change_excluded_even_if_reverted_before_settlement(self):
		doc = self.order("-reverted", -2, delivered_qty=0)
		due = doc.items[0].delivery_date
		name = self.freeze(doc, due - timedelta(days=1))
		doc.items[0].qty = 20
		self.freeze(doc, due)
		settle_batch([name], datetime.combine(self.day, time(8)))
		self.assertEqual(frappe.db.get_value(PROMISE, name, "outcome"), "Excluded")

	def test_one_full_day_for_backdated_dispatch_postings(self):
		doc = self.order("-grace", -1, delivered_qty=0)
		name = self.freeze(doc, doc.items[0].delivery_date)
		settle_batch([name], datetime.combine(self.day, time(23)))
		self.assertEqual(frappe.db.get_value(PROMISE, name, "outcome"), "Pending")
		settle_batch([name], datetime.combine(self.day + timedelta(days=1), time(0)))
		self.assertEqual(frappe.db.get_value(PROMISE, name, "outcome"), "Missed")

	def test_capped_worklist_checks_earliest_promises_first(self):
		later = self.order("-a-later", 6)
		earlier = self.order("-z-sooner", -29)
		with patch("ai_lead_assistant.dispatch.api.PARENT_LIMIT", 1):
			view = get_watchlist()
		self.assertTrue(view["truncated"])
		self.assertIn(earlier.name, [r["order"] for r in view["rows"]])
		self.assertNotIn(later.name, [r["order"] for r in view["rows"]])

	def test_stock_comparison_uses_recorded_warehouse_and_stock_units(self):
		doc = self.order("-stock", warehouse=self.prefix)
		self.record("Bin", "-bin", warehouse=self.prefix, item_code="DW-VALVE", stock_uom="Nos", actual_qty=5)
		row = next(r for r in get_watchlist()["rows"] if r["order"] == doc.name)
		self.assertEqual(row["stock"], {"needed": 16, "on_hand": 5, "short": 11, "uom": "Nos"})
		self.assertIn("falls short by 11 Nos", str(run(FEATURE, "Sales Order", doc.name)))
		with patch.object(frappe.get_meta("Bin").get_field("actual_qty"), "permlevel", 8):
			redacted = next(r for r in get_watchlist()["rows"] if r["order"] == doc.name)
		self.assertNotIn("stock", redacted)
		self.assertEqual(coverage(row, -4)["short"], 16)

	def test_settlement_compares_original_date_and_normalizes_source_units(self):
		doc = self.order("-settle", -2, delivered_qty=0)
		due = doc.items[0].delivery_date
		snap = self.freeze(doc, due - timedelta(days=1))
		line = doc.items[0]
		frappe.db.set_value(
			line.doctype, line.name, {"delivered_qty": 10, "delivery_date": self.day + timedelta(days=3)}
		)
		dn = dict(
			so_detail=line.name,
			against_sales_order=doc.name,
			item_code=line.item_code,
			stock_uom="Nos",
			qty=3,
			conversion_factor=2,
		)
		si = dict(
			so_detail=line.name,
			sales_order=doc.name,
			item_code=line.item_code,
			stock_uom="Nos",
			qty=14,
			conversion_factor=1,
		)
		self.record("Delivery Note", "-dn", docstatus=1, posting_date=due, items=[dn])
		self.record(
			"Sales Invoice",
			"-si",
			docstatus=1,
			update_stock=1,
			posting_date=due + timedelta(days=1),
			items=[si],
		)
		self.record("Sales Invoice", "-bill", docstatus=1, update_stock=0, posting_date=due, items=[si])
		self.record("Delivery Note", "-draft", docstatus=0, posting_date=due, items=[dn])
		self.assertEqual(len(movement_map([line.name])[line.name]), 2)
		settle_batch([snap], datetime.combine(self.day, time(8)))
		result = frappe.get_doc(PROMISE, snap)
		self.assertEqual(result.outcome, "Missed")
		self.assertIn("3 of 10 Pair", result.outcome_note)
		frappe.db.set_value(line.doctype, line.name, "qty", 20)
		settle_batch([snap], datetime.combine(self.day, time(9)))
		self.assertEqual(frappe.db.get_value(PROMISE, snap, "outcome_note"), result.outcome_note)

	def test_uncertain_returns_amendments_and_unlinked_dispatch_are_excluded(self):
		for i, case in enumerate(("return", "changed", "unlinked", "cancelled", "on time", "none")):
			doc = self.order("-case" + str(i), -2, delivered_qty=0)
			line = doc.items[0]
			snap = self.freeze(doc, line.delivery_date)
			dn = dict(
				so_detail=line.name,
				against_sales_order=doc.name,
				item_code=line.item_code,
				stock_uom="Nos",
				qty=20,
				conversion_factor=1,
			)
			if case in ("return", "on time"):
				self.record(
					"Delivery Note",
					"-case-dn" + str(i),
					docstatus=1,
					is_return=int(case == "return"),
					posting_date=line.delivery_date,
					items=[dn],
				)
				frappe.db.set_value(line.doctype, line.name, "delivered_qty", 10)
			if case == "changed":
				frappe.db.set_value(line.doctype, line.name, "qty", 22)
			if case == "unlinked":
				frappe.db.set_value(line.doctype, line.name, "delivered_qty", 1)
			if case == "cancelled":
				frappe.db.set_value("Sales Order", doc.name, "docstatus", 2)
			settle_batch([snap], datetime.combine(self.day, time(8)))
			want = {"on time": "On time", "none": "Missed"}.get(case, "Excluded")
			self.assertEqual(frappe.db.get_value(PROMISE, snap, "outcome"), want, case)

	def test_permission_filtered_history_live_and_sample_isolation(self):
		pub = self.order("-shared", warehouse=self.prefix)
		self.record("Bin", "-bin", item_code="DW-VALVE", warehouse=self.prefix, stock_uom="Nos", actual_qty=3)
		private = self.order("-private")
		self.freeze(pub)
		self.freeze(private)
		initial = frappe.db.count(PROMISE)
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": self.prefix.lower() + "@example.invalid",
				"first_name": "Dispatch",
				"send_welcome_email": 0,
				"roles": [{"role": "Employee"}],
			}
		).insert()
		frappe.share.add("Sales Order", pub.name, user.name, read=1)
		frappe.set_user(user.name)
		self.assertIn(FEATURE, get_form_features("Sales Order", pub.name))
		data = get_watchlist()
		self.assertIn(pub.name, str(data))
		self.assertNotIn("stock", data["rows"][0])
		self.assertNotIn(private.name, str(data))
		self.assertEqual(data["history"]["observed"], 1)
		self.assertFalse(frappe.has_permission(PROMISE, "read"))
		with patch.object(frappe.get_meta("Sales Order Item").get_field("delivered_qty"), "permlevel", 8):
			self.assertFalse(get_watchlist()["accessible"])
			self.assertEqual(get_watchlist()["history"]["observed"], 0)
		with (
			patch("ai_lead_assistant.dispatch.api._live") as live,
			patch("ai_lead_assistant.dispatch.api._visible_history") as historical,
		):
			sample = get_watchlist(1)
			live.assert_not_called()
			historical.assert_not_called()
		self.assertTrue(sample["sample"])
		self.assertTrue(sample["history"]["comparison"]["days"])
		self.assertNotIn(pub.name, str(sample))
		self.assertEqual(frappe.db.count(PROMISE), initial)
