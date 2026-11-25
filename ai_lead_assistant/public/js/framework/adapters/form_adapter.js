import "../assignment_changes";
import { createFormContext } from "../context";
import registry from "../registry";

class FormAdapter {
    constructor(manager) {
        this.manager = manager;
        this.refreshes = new WeakMap();
        $(document).on("form-load", (_, frm) => {
            if (registry.getExtensions().some(extension => extension.onLoad)) this.handle("load", frm);
        });
        $(document).on("form-refresh", (_, frm) => this.handle("refresh", frm));
        const refreshActiveForm = () => {
            if (frappe.get_route()[0] === "Form" && window.cur_frm) this.handle("refresh", cur_frm);
        };
        $(document).on("ai-feature-assignments-refresh", refreshActiveForm);
    }

    async handle(event, frm) {
        if (!frappe.boot.ai_extension_modules?.includes(frm.meta.module)) return;
        const context = createFormContext(event, frm);
        const request = {};
        if (event === "refresh") this.refreshes.set(frm, request);
        const args = { doctype: frm.doctype };
        if (!frm.is_new()) args.document_name = frm.docname;
        let allowed = [];
        try {
            const response = await frappe.call({
                method: "ai_lead_assistant.framework.assignments.get_form_features",
                args,
            });
            allowed = response.message || [];
        } catch (error) {
            console.error("Could not load AI feature assignments.", error);
        }
        if (frm.doc !== context.doc || (event === "refresh" && this.refreshes.get(frm) !== request)) return;
        this.manager.handle(context, allowed);
    }
}

export default FormAdapter;
