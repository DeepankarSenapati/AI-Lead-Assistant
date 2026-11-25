import unittest
from unittest.mock import patch

import frappe

from ai_lead_assistant.api import process_document
from ai_lead_assistant.framework.assignments import RULE, get_dashboard, get_form_features, set_assignment


class TestAIFeatureAssignment(unittest.TestCase):
    def setUp(self):
        self.addCleanup(frappe.set_user, frappe.session.user)
        frappe.set_user("Administrator")
        frappe.db.savepoint("ai_assignment_test")
        self.addCleanup(frappe.db.rollback, save_point="ai_assignment_test")
        frappe.db.delete(RULE)

    def test_catalog_uses_installed_erpnext_forms(self):
        forms = {row.name: row.module for row in get_dashboard()["forms"]}
        self.assertEqual(forms["Lead"], "CRM")
        self.assertEqual(forms["Purchase Receipt"], "Stock")
        for excluded in ("Purchase Receipt Item", "Selling Settings", "User"):
            self.assertNotIn(excluded, forms)

    def test_form_overrides_module_and_can_inherit_again(self):
        set_assignment("chat_assistant", "DocType", "Lead", "off")
        set_assignment("chat_assistant", "Module Def", "CRM", "on")
        self.assertNotIn("chat_assistant", get_form_features("Lead"))
        self.assertIn("chat_assistant", get_form_features("Opportunity"))
        self.assertNotIn("chat_assistant", get_form_features("Item"))
        set_assignment("chat_assistant", "DocType", "Lead", "inherit")
        self.assertIn("chat_assistant", get_form_features("Lead"))

    def test_same_feature_on_separate_forms_and_retry(self):
        for target in ("Lead", "Item", "Lead"):
            set_assignment("chat_assistant", "DocType", target, "on")
        self.assertEqual(frappe.db.count(RULE), 2)
        self.assertIn("chat_assistant", get_form_features("Item"))
        self.assertEqual(set(get_form_features("Lead")), {"chat_assistant", "form_assistant"})

    def test_form_fill_applies_only_to_mapped_forms(self):
        for target in ("Lead", "Purchase Receipt"):
            self.assertIn("form_assistant", get_form_features(target))
        set_assignment("form_assistant", "Module Def", "CRM", "on")
        self.assertNotIn("form_assistant", get_form_features("Opportunity"))
        for scope, target in (("DocType", "Opportunity"), ("Module Def", "Assets"), ("DocType", "User")):
            with self.assertRaises(frappe.ValidationError):
                set_assignment("form_assistant", scope, target, "on")

    def test_unassigned_form_fill_refuses_extraction(self):
        set_assignment("form_assistant", "DocType", "Lead", "off")
        with patch("ai_lead_assistant.api.file_service.get_uploaded_file") as read_file:
            with self.assertRaises(frappe.PermissionError):
                process_document("/private/files/example.pdf", "Lead")
            read_file.assert_not_called()

    def test_edit_permission_and_read_permission_are_independent(self):
        set_assignment("chat_assistant", "DocType", "Lead", "on")
        with patch("ai_lead_assistant.framework.assignments.document_access", return_value=(True, False)):
            self.assertEqual(get_form_features("Lead"), ["chat_assistant"])
        with patch("ai_lead_assistant.framework.assignments.document_access", return_value=(False, False)):
            self.assertEqual(get_form_features("Lead"), [])

    def test_management_requires_system_manager(self):
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            get_dashboard()
        with self.assertRaises(frappe.PermissionError):
            set_assignment("chat_assistant", "DocType", "Lead", "on")
