from types import SimpleNamespace
from unittest.mock import patch

import frappe

from ai_lead_assistant.extensions import transaction_followup
from ai_lead_assistant.extensions.test_insights import InsightTestCase
from ai_lead_assistant.framework.assignments import get_dashboard, get_form_features, set_assignment
from ai_lead_assistant.framework.insights import run

FEATURE = "transaction_followup"


class TestTransactionFollowup(InsightTestCase):
	def brief(self, doc):
		self.assign(FEATURE, doc.doctype)
		return run(FEATURE, doc.doctype, doc.name)

	def test_catalog_and_overrides(self):
		card = next(f for f in get_dashboard()["features"] if f["id"] == FEATURE)
		self.assertEqual(
			set(card["forms"]),
			{
				"Sales Order",
				"Purchase Order",
				"Sales Invoice",
				"Purchase Invoice",
				"Delivery Note",
				"Purchase Receipt",
			},
		)
		set_assignment(FEATURE, "Module Def", "Stock", "on")
		self.assertIn(FEATURE, get_form_features("Delivery Note"))
		self.assertNotIn(FEATURE, get_form_features("Item"))
		set_assignment(FEATURE, "DocType", "Delivery Note", "off")
		self.assertNotIn(FEATURE, get_form_features("Delivery Note"))
		with self.assertRaises(frappe.ValidationError):
			set_assignment(FEATURE, "Module Def", "CRM", "on")
		with self.assertRaises(frappe.ValidationError):
			run(FEATURE, "Purchase Receipt")

	def test_sales_order_urgent_lines_and_submitted_links(self):
		line = {
			"qty": 10,
			"uom": "Box",
			"delivered_qty": 4,
			"item_code": "QA-RIVET",
			"delivery_date": "2020-01-02",
		}
		order = self.record(
			"Sales Order",
			"-order",
			docstatus=1,
			status="To Deliver",
			per_delivered=40,
			per_billed=100,
			items=[
				line,
				{**line, "item_code": "DROP-SHIP", "delivered_by_supplier": 1},
				{**line, "item_code": "FINISHED", "delivered_qty": 10},
			],
		)
		shipped = self.record(
			"Delivery Note",
			"-delivery",
			docstatus=1,
			status="To Bill",
			items=[{"against_sales_order": order.name}] * 2,
		)
		draft = self.record("Sales Invoice", "-draft", docstatus=0, items=[{"sales_order": order.name}])
		cancelled = self.record(
			"Delivery Note", "-cancelled", docstatus=2, items=[{"against_sales_order": order.name}]
		)
		brief = self.brief(order)
		self.assertIn("40% delivered by quantity", str(brief))
		self.assertIn("100% billed by amount", str(brief))
		self.assertIn("6 Box still to deliver", str(brief))
		self.assertEqual(sum(f["name"] == shipped.name for f in brief["findings"]), 1)
		for unwanted in (draft.name, cancelled.name, "FINISHED", "DROP-SHIP"):
			self.assertNotIn(unwanted, str(brief))
		for status, skip in [("On Hold", 0), ("Closed", 0), ("Completed", 0), ("To Bill", 1)]:
			frappe.db.set_value(order.doctype, order.name, {"status": status, "skip_delivery_note": skip})
			self.assertNotIn("still to deliver", str(run(FEATURE, order.doctype, order.name)))

	def test_purchase_chain_both_directions_and_returns(self):
		order = self.record(
			"Purchase Order",
			"-po",
			docstatus=1,
			status="To Receive and Bill",
			per_received=50,
			per_billed=0,
			items=[
				{
					"item_code": "WASHER",
					"qty": 8,
					"received_qty": 4,
					"uom": "Pair",
					"schedule_date": "2020-01-02",
				}
			],
		)
		receipt = self.record(
			"Purchase Receipt",
			"-pr",
			docstatus=1,
			status="To Bill",
			per_billed=25,
			items=[{"purchase_order": order.name}],
		)
		invoice = self.record(
			"Purchase Invoice",
			"-pi",
			docstatus=1,
			status="Partly Paid",
			currency="USD",
			party_account_currency="INR",
			outstanding_amount=357,
			items=[{"purchase_receipt": receipt.name, "purchase_order": order.name}],
		)
		returned = self.record(
			"Purchase Receipt",
			"-return",
			docstatus=1,
			is_return=1,
			status="Return",
			return_against=receipt.name,
		)
		self.assertIn("4 Pair still to receive", str(self.brief(order)))
		brief = self.brief(receipt)
		self.assertIn("25% billed by amount", str(brief))
		self.assertEqual(
			{f["name"] for f in brief["findings"]}, {order.name, receipt.name, invoice.name, returned.name}
		)
		invoice_brief = self.brief(invoice)
		self.assertIn("INR 357", str(invoice_brief))
		self.assertNotIn("USD", str(invoice_brief))
		self.assertEqual(
			{f["name"] for f in invoice_brief["findings"]}, {order.name, receipt.name, invoice.name}
		)
		self.assertIn(receipt.name, str(self.brief(returned)))
		self.assertNotIn("Compare the unbilled", str(self.brief(returned)))

	def test_due_dates_invoice_holds_and_update_stock(self):
		invoice = self.record(
			"Purchase Invoice",
			"-overdue",
			docstatus=1,
			status="Overdue",
			update_stock=1,
			outstanding_amount=300,
			currency="USD",
			party_account_currency="USD",
			due_date="2027-01-01",
			payment_schedule=[
				{"due_date": "2020-01-01", "payment_amount": 100},
				{"due_date": "2027-01-01", "payment_amount": 200},
			],
		)
		brief = self.brief(invoice)
		self.assertIn("portion currently due", str(brief))
		self.assertIn("Update Stock", str(brief))
		frappe.db.set_value(invoice.doctype, invoice.name, "on_hold", 1)
		self.assertIn("Payment is on hold", str(self.brief(invoice)))
		self.assertNotIn("portion currently due", str(self.brief(invoice)))
		frappe.db.set_value(invoice.doctype, invoice.name, {"docstatus": 0, "status": "Draft"})
		self.assertNotIn("300", str(self.brief(invoice)["findings"]))
		self.assertNotIn("Update Stock", str(self.brief(invoice)))

	def test_reverse_link_permissions(self):
		# A user with only a share on the order must never see a linked invoice's identifier.
		order = self.record("Sales Order", "-shared", docstatus=1, status="To Deliver")
		invoice = self.record("Sales Invoice", "-private", docstatus=1, items=[{"sales_order": order.name}])
		self.assign(FEATURE, order.doctype)
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": self.prefix.lower() + "@example.invalid",
				"first_name": "Reader",
				"send_welcome_email": 0,
				"roles": [{"role": "Employee"}],
			}
		).insert()
		frappe.share.add(order.doctype, order.name, user.name, read=1)
		frappe.set_user(user.name)
		self.assertTrue(frappe.has_permission(order.doctype, "read", order.name))
		self.assertFalse(frappe.has_permission(invoice.doctype, "read", invoice.name))
		brief = run(FEATURE, order.doctype, order.name)
		self.assertIn(order.name, str(brief))
		self.assertNotIn(invoice.name, str(brief))

	def test_only_reviewed_evidence_can_be_drafted(self):
		invoice = self.record(
			"Sales Invoice", "-si", docstatus=1, status="Paid", remarks="UNREVIEWED PRIVATE DETAIL"
		)
		with patch.dict(frappe.conf, {"openai_api_key": "test-only"}), patch("openai.OpenAI") as client:
			brief = self.brief(invoice)
			self.assertTrue(brief["can_draft"])
			client.return_value.chat.completions.create.return_value = SimpleNamespace(
				choices=[SimpleNamespace(message=SimpleNamespace(content="The invoice is paid [1]."))]
			)
			result = transaction_followup.draft(invoice.doctype, invoice.name, brief["version"])
			self.assertEqual(result["findings"], brief["findings"])
			self.assertNotIn("UNREVIEWED", str(client.return_value.chat.completions.create.call_args))
			frappe.db.set_value(invoice.doctype, invoice.name, "status", "Overdue")
			with self.assertRaises(frappe.ValidationError):
				transaction_followup.draft(invoice.doctype, invoice.name, brief["version"])
			set_assignment(FEATURE, "DocType", invoice.doctype, "off")
			with self.assertRaises(frappe.PermissionError):
				transaction_followup.draft(invoice.doctype, invoice.name, brief["version"])
			self.assertEqual(client.call_count, 1)

	def test_field_permissions_apply_to_both_link_directions_and_amounts(self):
		order = self.record("Sales Order", "-so", docstatus=1, status="To Bill")
		invoice = self.record(
			"Sales Invoice",
			"-si",
			docstatus=1,
			status="Unpaid",
			party_account_currency="USD",
			outstanding_amount=9123,
			items=[{"sales_order": order.name}],
		)
		for doc in (order, invoice):
			self.assign(FEATURE, doc.doctype)
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": self.prefix.lower() + "@example.invalid",
				"first_name": "Sales and Accounts",
				"send_welcome_email": 0,
				"roles": [{"role": "Sales Manager"}, {"role": "Accounts Manager"}],
			}
		).insert()
		frappe.set_user(user.name)

		def names(doc):
			return {f["name"] for f in run(FEATURE, doc.doctype, doc.name)["findings"]}

		self.assertIn(order.name, names(invoice))
		self.assertIn(invoice.name, names(order))
		# Model a site's restricted DocFields without writing shared customization or clearing other users' caches.
		with patch.object(frappe.get_meta("Sales Invoice").get_field("outstanding_amount"), "permlevel", 8):
			self.assertNotIn("9,123", str(run(FEATURE, order.doctype, order.name)))
			self.assertNotIn("Outstanding balance", str(run(FEATURE, invoice.doctype, invoice.name)))
		with patch.object(frappe.get_meta("Sales Invoice Item").get_field("sales_order"), "permlevel", 8):
			self.assertNotIn(invoice.name, names(order))
			self.assertNotIn(order.name, names(invoice))

	def test_direct_invoices_without_links_and_source_limits(self):
		order = self.record("Sales Order", "-order", docstatus=1, status="To Bill")
		direct = self.record(
			"Sales Invoice",
			"-direct",
			docstatus=1,
			status="Unpaid",
			update_stock=1,
			items=[{"item_code": "RIVET"}],
		)
		self.assertEqual({f["name"] for f in self.brief(direct)["findings"]}, {direct.name})
		for i in range(5):
			self.record(
				"Sales Invoice", f"-si{i}", docstatus=1, status="Paid", items=[{"sales_order": order.name}]
			)
		matches = [f for f in self.brief(order)["findings"] if f["doctype"] == "Sales Invoice"]
		self.assertEqual(len({f["name"] for f in matches}), 3)
		self.assertNotIn(direct.name, {f["name"] for f in matches})
