"""Exercise the Desk endpoints against real v15 records without posting transactions."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from ai_lead_assistant.extensions import crm_handoff, duplicate_finder, invoice_review
from ai_lead_assistant.framework.assignments import set_assignment
from ai_lead_assistant.framework.insights import run


class InsightTestCase(unittest.TestCase):
	def setUp(self):
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user("Administrator")
		frappe.db.savepoint("insight_test")
		self.addCleanup(frappe.db.rollback, save_point="insight_test")
		self.prefix = "AI-QA-" + frappe.generate_hash(length=8)
		self.company = frappe.db.get_value("Company", {}, "name") or self.prefix

	def record(self, doctype, suffix, **data):
		# Use real parent and child tables but skip posting, email and scheduler hooks.
		document = frappe.get_doc({"doctype": doctype, "name": self.prefix + suffix, **data})
		document.db_insert()
		for child in document.get_all_children():
			child.parent = document.name
			child.db_insert()
		return document

	def assign(self, feature, doctype):
		set_assignment(feature, "DocType", doctype, "on")


class TestInsights(InsightTestCase):
	def test_duplicate_name_and_identifiers_work_before_save(self):
		self.assign("duplicate_finder", "Customer")
		customer = self.record(
			"Customer", "-cust", customer_name="Aster Quench Manufacturing", tax_id="TX-147-399"
		)
		for query in ["Aster Quench Manufacturinng", "TX147399"]:
			result = run("duplicate_finder", "Customer", query=query)
			self.assertIn(customer.name, [r["name"] for r in result["findings"]])
		result = run("duplicate_finder", "Customer", customer.name)
		self.assertNotIn(customer.name, [r["name"] for r in result["findings"]])

	def test_identifier_match_survives_a_crowded_name_search(self):
		self.assign("duplicate_finder", "Customer")
		saved = self.record("Customer", "-input", customer_name="Indigo Loom", tax_id="IN-12-3456")
		self.record("Customer", "-first", customer_name="Indigo Weavers")
		exact = self.record("Customer", "-match", customer_name="Aster Textiles", tax_id="IN123456")
		self.record("Customer", "-last", customer_name="Indigo Yarn")
		with patch.object(duplicate_finder, "FETCH_LIMIT", 1):
			report = run("duplicate_finder", "Customer", saved.name)
		self.assertEqual(report["findings"][0]["name"], exact.name)

	def test_different_part_numbers_stay_distinct(self):
		self.assign("duplicate_finder", "Item")
		item = self.record("Item", "-item", item_code="SLV-204", item_name="Zircon Sleeve 204")
		matches = run("duplicate_finder", "Item", query="Zircon Sleeve 402")["findings"]
		self.assertNotIn(item.name, [r["name"] for r in matches])
		self.assertIn(
			item.name, [r["name"] for r in run("duplicate_finder", "Item", query="SLV-204")["findings"]]
		)

	def test_search_obeys_customer_user_permissions(self):
		self.assign("duplicate_finder", "Customer")
		permitted = self.record("Customer", "-visible", customer_name="Quartz Aster")
		private = self.record("Customer", "-private", customer_name="Quartz Aster Limited")
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": self.prefix.lower() + "@example.invalid",
				"first_name": "Insight QA",
				"send_welcome_email": 0,
				"roles": [{"role": "Sales User"}],
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": user.name,
				"allow": "Customer",
				"for_value": permitted.name,
				"apply_to_all_doctypes": 1,
			}
		).insert()
		frappe.set_user(user.name)
		result = run("duplicate_finder", "Customer", permitted.name, query="Quartz Aster")
		self.assertNotIn(private.name, str(result))
		with self.assertRaises(frappe.PermissionError):
			run("duplicate_finder", "Customer", private.name, query="Quartz Aster")

	def test_support_returns_recorded_resolution_and_skips_open_or_self(self):
		self.assign("similar_issues", "Issue")
		subject = "Indigo spindle encoder ERR-7309"
		resolved = self.record(
			"Issue",
			"-closed",
			subject=subject,
			status="Resolved",
			resolution_details="<p>Reseated the encoder cable.</p>",
		)
		current = self.record("Issue", "-self", subject=subject, status="Closed")
		reopened = self.record("Issue", "-open", subject=subject, status="Open")
		results = run("similar_issues", "Issue", current.name)["findings"]
		self.assertIn(resolved.name, [r["name"] for r in results])
		self.assertNotIn(reopened.name, [r["name"] for r in results])
		self.assertNotIn(current.name, [r["name"] for r in results])
		hit = next(r for r in results if r["name"] == resolved.name)
		self.assertIn("Reseated the encoder cable.", hit["detail"])
		self.assertNotIn("<p>", hit["detail"])
		self.assertIn(
			resolved.name, [r["name"] for r in run("similar_issues", "Issue", query="ERR-7309")["findings"]]
		)
		self.assertEqual(run("similar_issues", "Issue", query="error help")["findings"], [])

	def test_crm_notes_tasks_and_plain_text_sources(self):
		self.assign("crm_handoff", "Lead")
		lead = self.record(
			"Lead",
			"-lead",
			company_name="Indigo Textile",
			status="Open",
			notes=[{"note": "<p>Met the buyer. Send the revised quote by Friday.</p>"}],
		)
		task = self.record(
			"ToDo",
			"-task",
			reference_type="Lead",
			reference_name=lead.name,
			status="Open",
			date="2020-01-02",
			description="Confirm sample quantity.",
		)
		done = self.record(
			"ToDo",
			"-done",
			reference_type="Lead",
			reference_name=lead.name,
			status="Closed",
			description="This task is finished.",
		)
		brief = run("crm_handoff", "Lead", lead.name)
		self.assertIn("Send the revised quote by Friday.", str(brief["findings"]))
		self.assertNotIn("Met the buyer.", str(brief["findings"]))
		self.assertNotIn(done.name, str(brief["findings"]))
		self.assertEqual(next(r for r in brief["findings"] if r["name"] == task.name)["level"], "warning")
		self.assertIn("Indigo Textile", brief["summary"])

	def test_handoff_draft_uses_reviewed_sources_only(self):
		self.assign("crm_handoff", "Opportunity")
		op = self.record(
			"Opportunity", "-op", status="Open", currency="INR", notes=[{"note": "Send samples."}]
		)
		with patch.dict(frappe.conf, {"openai_api_key": "test-only"}), patch("openai.OpenAI") as client:
			brief = run("crm_handoff", "Opportunity", op.name)
			with self.assertRaises(frappe.ValidationError):
				crm_handoff.draft("Opportunity", op.name, "stale")
			client.assert_not_called()
			client.return_value.chat.completions.create.return_value = SimpleNamespace(
				choices=[SimpleNamespace(message=SimpleNamespace(content="Send samples [2]."))]
			)
			draft = crm_handoff.draft("Opportunity", op.name, brief["version"])
			self.assertEqual(draft["findings"], brief["findings"])
			self.assertIn("[2]", draft["text"])
			call = client.return_value.chat.completions.create.call_args.kwargs
			self.assertIn("Send samples.", call["messages"][1]["content"])
			self.assertNotIn("test-only", str(call))
			set_assignment("crm_handoff", "DocType", "Opportunity", "off")
			with self.assertRaises(frappe.PermissionError):
				crm_handoff.draft("Opportunity", op.name, brief["version"])
			self.assertEqual(client.call_count, 1)

	def purchasing(self, *, source_rate=20, source_currency="INR", quantities=(3, 4), invoice_rate=11):
		self.assign("invoice_review", "Purchase Invoice")
		common = {"company": self.company, "supplier": self.prefix + " Supplier", "currency": "INR"}
		item = {"item_code": "QA-FASTENER", "stock_uom": "Nos"}
		source = self.record(
			"Purchase Receipt",
			"-pr",
			**{**common, "currency": source_currency},
			docstatus=1,
			items=[
				{**item, "qty": 3, "uom": "Pair", "conversion_factor": 2, "stock_qty": 6, "rate": source_rate}
			],
		)
		invoice = self.record(
			"Purchase Invoice",
			"-pi",
			**common,
			items=[
				{
					**item,
					"qty": qty,
					"uom": "Nos",
					"conversion_factor": 1,
					"stock_qty": qty,
					"rate": invoice_rate,
					"purchase_receipt": source.name,
					"pr_detail": source.items[0].name,
				}
				for qty in quantities
			],
		)
		return source, invoice

	def test_invoice_checks_shared_receipt_row_and_normalized_price(self):
		source, invoice = self.purchasing()
		report = run("invoice_review", "Purchase Invoice", invoice.name)
		finding = next(r for r in report["findings"] if r.get("name") == source.name)
		self.assertIn("7 Nos", finding["detail"])
		self.assertIn("6 Nos", finding["detail"])
		self.assertIn("11", finding["detail"])
		self.assertIn("10", finding["detail"])
		self.assertEqual(finding["level"], "warning")

	def test_invoice_partial_bill_and_currency(self):
		source, invoice = self.purchasing(quantities=(2,), source_currency="USD", invoice_rate=999)
		report = run("invoice_review", "Purchase Invoice", invoice.name)
		self.assertFalse(any(r.get("level") == "warning" for r in report["findings"]))
		self.assertIn("currency", report["note"])
		with patch("ai_lead_assistant.extensions.invoice_review.readable_doc", return_value=None):
			findings = run("invoice_review", "Purchase Invoice", invoice.name)["findings"]
		self.assertFalse(any(r.get("name") == source.name for r in findings))

	def test_incomplete_invoice_review_never_reports_clean(self):
		_, invoice = self.purchasing(quantities=(1, 2), invoice_rate=10)
		with patch.object(invoice_review, "MAX_LINES", 1):
			report = run("invoice_review", "Purchase Invoice", invoice.name)
		self.assertIn("line cap", report["note"])
		self.assertFalse(any(f.get("level") == "success" for f in report["findings"]))

	def test_invoice_missing_or_incompatible_source_units(self):
		source, invoice = self.purchasing()
		frappe.db.set_value("Purchase Receipt Item", source.items[0].name, "stock_uom", "Kg")
		report = run("invoice_review", "Purchase Invoice", invoice.name)
		self.assertIn("stock unit", str(report["findings"]))
		self.assertNotIn("unit price", str(report["findings"]))
		self.assertNotIn("alone bills more", str(report["findings"]))
		frappe.db.set_value("Purchase Receipt", source.name, "docstatus", 2)
		report = run("invoice_review", "Purchase Invoice", invoice.name)
		self.assertIn("0 linked", report["summary"])
		self.assertIn("cancelled", str(report["findings"]))

	def test_saved_record_and_assignment_enforcement(self):
		self.assign("crm_handoff", "Lead")
		with self.assertRaises(frappe.ValidationError):
			run("crm_handoff", "Lead")
		with self.assertRaises(frappe.ValidationError):
			run("invoice_review", "Lead")
		set_assignment("duplicate_finder", "DocType", "Customer", "off")
		with self.assertRaises(frappe.PermissionError):
			run("duplicate_finder", "Customer", query="Indigo Quench")
