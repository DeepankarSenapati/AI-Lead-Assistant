import frappe
from frappe import _

from ai_lead_assistant.extensions import FEATURES


RULE = "AI Feature Assignment"
FORM_FILTERS = {"istable": 0, "issingle": 0, "is_virtual": 0}


def erp_modules():
    return frappe.get_all("Module Def", filters={"app_name": "erpnext"}, pluck="name")


def boot_session(bootinfo):
    bootinfo.ai_extension_modules = erp_modules()
    bootinfo.ai_insight_features = [f.client_spec(key) for key, f in FEATURES.items() if f.analyzer]


def form_module(doctype):
    meta = frappe.get_cached_doc("DocType", doctype)
    if any(meta.get(field) for field in FORM_FILTERS):
        return None
    if frappe.get_cached_value("Module Def", meta.module, "app_name") == "erpnext":
        return meta.module
    return None


def rules_for(module, doctype):
    rows = frappe.get_all(
        RULE,
        filters={"target": ["in", [module, doctype]]},
        fields=["feature", "target_type", "target", "enabled"],
    )
    return {(r.feature, r.target_type, r.target): bool(r.enabled) for r in rows}


def enabled(feature_id, module, doctype, rules):
    feature = FEATURES[feature_id]
    if not module or not feature.supports(doctype):
        return False
    module_default = rules.get((feature_id, "Module Def", module), feature.default_enabled)
    return rules.get((feature_id, "DocType", doctype), module_default)


def document_access(doctype, document_name):
    if document_name:
        doc = frappe.get_doc(doctype, document_name)
        return doc.has_permission("read"), not doc.docstatus and doc.has_permission("write")
    can_create = frappe.has_permission(doctype, "create")
    return can_create, can_create


@frappe.whitelist()
def get_form_features(doctype: str, document_name: str | None = None):
    module = form_module(doctype)
    if not module:
        return []
    readable, editable = document_access(doctype, document_name)
    if not readable:
        return []
    rules = rules_for(module, doctype)
    return [
        key for key, feature in FEATURES.items()
        if enabled(key, module, doctype, rules) and (editable or not feature.requires_edit)
    ]


def require_form_feature(feature_id, doctype, document_name):
    if feature_id not in get_form_features(doctype, document_name):
        frappe.throw(_("This feature is unavailable on this form."), frappe.PermissionError)


def require_manager():
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only a System Manager can manage AI features."), frappe.PermissionError)


@frappe.whitelist()
def get_dashboard():
    require_manager()
    forms = frappe.get_all(
        "DocType", filters={**FORM_FILTERS, "module": ["in", erp_modules()]},
        fields=["name", "module"], order_by="module, name",
    )
    return {
        "features": [feature.client_spec(key) for key, feature in FEATURES.items()],
        "forms": forms,
        "rules": frappe.get_all(RULE, fields=["feature", "target_type", "target", "enabled"]),
    }


@frappe.whitelist(methods=["POST"])
def set_assignment(feature: str, target_type: str, target: str, state: str):
    require_manager()
    if feature not in FEATURES or target_type not in ("Module Def", "DocType"):
        frappe.throw(_("Unknown feature or target type."))
    if state not in ("on", "off", "inherit"):
        frappe.throw(_("Unknown assignment state."))

    # Serialize concurrent changes to the same target, including the first insert.
    if not frappe.db.get_value(target_type, target, "name", for_update=True):
        frappe.throw(_("The selected target no longer exists."))
    definition = FEATURES[feature]
    if target_type == "Module Def":
        if target not in erp_modules():
            frappe.throw(_("Choose an ERPNext module."))
        filters = {**FORM_FILTERS, "module": target}
        if definition.forms is not None:
            filters["name"] = ["in", list(definition.forms)]
        if not frappe.db.exists("DocType", filters):
            frappe.throw(_("This feature has no compatible forms in this module."))
    elif not form_module(target) or not definition.supports(target):
        frappe.throw(_(definition.unavailable_reason or "This feature requires an ERPNext document form."))

    key = {"feature": feature, "target_type": target_type, "target": target}
    name = frappe.db.get_value(RULE, key, "name", for_update=True)
    if state == "inherit":
        if name:
            frappe.delete_doc(RULE, name, ignore_permissions=True)
    elif name:
        frappe.db.set_value(RULE, name, "enabled", int(state == "on"))
    else:
        frappe.get_doc({"doctype": RULE, **key, "enabled": int(state == "on")}).insert(ignore_permissions=True)
    frappe.publish_realtime("ai_feature_assignment_changed", after_commit=True)
