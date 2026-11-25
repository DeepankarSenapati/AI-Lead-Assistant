function showFindings(root, result) {
    root.empty();
    $("<h5>").text(result.summary).appendTo(root);
    for (const [index, item] of result.findings.entries()) {
        const row = $("<section>", { class: "border-bottom py-3" }).appendTo(root);
        const title = $("<strong>").text(item.title);
        if (item.level === "warning") title.addClass("text-warning");
        row.append(title);
        $("<div>", { class: "mt-1" }).text(item.detail).appendTo(row);
        if (item.doctype && item.name) {
            $("<a>", { href: frappe.utils.get_form_link(item.doctype, item.name), target: "_blank",
                rel: "noopener noreferrer", class: "small" })
                .text(__("Source {0} · {1}", [index + 1, item.name])).appendTo(row);
        }
    }
    if (result.note) $("<p>", { class: "mt-3 text-muted small" }).text(result.note).appendTo(root);
}

export function openInsight(feature, frm) {
    if (feature.needs_saved && (frm.is_new() || frm.is_dirty())) {
        frappe.msgprint(__("Save your changes, then open {0} to review this version.", [__(feature.label)]));
        return;
    }
    const doc = frm.doc;
    const documentName = frm.is_new() ? null : doc.name;
    const seed = feature.query_label && (!documentName || frm.is_dirty())
        ? String(doc[frm.meta.title_field] || doc.company_name || doc.item_code || doc.first_name || "").slice(0, 500) : "";
    const fields = [];
    if (feature.query_label) {
        fields.push({ fieldtype: "Small Text", fieldname: "query", label: __(feature.query_label),
            default: seed, description: documentName ? __("Leave blank to use the saved record.") : "", reqd: !documentName });
    }
    fields.push({ fieldtype: "HTML", fieldname: "results" });
    const dialog = new frappe.ui.Dialog({ title: __(feature.label), fields, size: "large" });
    const root = dialog.fields_dict.results.$wrapper.attr("aria-live", "polite");
    let pending = false;

    async function run() {
        if (pending || frm.doc !== doc) return;
        const query = feature.query_label ? (dialog.get_value("query") || "").trim() : "";
        if (query.length > 500) {
            frappe.msgprint(__("Use a search of 500 characters or fewer."));
            return;
        }
        pending = true;
        dialog.get_primary_btn().prop("disabled", true);
        root.empty().text(__("Checking ERPNext records…"));
        try {
            const { message } = await frappe.call({
                method: "ai_lead_assistant.framework.insights.run",
                args: { feature: feature.id, doctype: frm.doctype, document_name: documentName, query },
            });
            showFindings(root, message);
            if (message.can_draft && feature.draft_method) {
                const draftButton = $("<button>", { type: "button", class: "btn btn-default btn-sm" })
                    .text(__("Draft handoff with OpenAI")).appendTo(root);
                $("<small>", { class: "d-block text-muted mt-1" })
                    .text(__("Sends the displayed sales context, task details and note excerpts to your configured OpenAI account."))
                    .appendTo(root);
                draftButton.on("click", async () => {
                    if (pending) return;
                    pending = true;
                    draftButton.prop("disabled", true);
                    dialog.get_primary_btn().prop("disabled", true);
                    try {
                        const { message: draft } = await frappe.call({
                            method: feature.draft_method, args: { doctype: frm.doctype, document_name: documentName, version: message.version },
                        });
                        showFindings(root, { ...message, findings: draft.findings });
                        const block = $("<section>", { class: "border rounded p-3 mb-3" }).prependTo(root);
                        $("<strong>").text(__("AI draft")).appendTo(block);
                        $("<p>", { class: "mt-2 mb-0" }).css("white-space", "pre-wrap").text(draft.text).appendTo(block);
                    } finally {
                        pending = false;
                        draftButton.prop("disabled", false);
                        dialog.get_primary_btn().prop("disabled", false);
                    }
                });
            }
        } catch (error) {
            root.text(__("The review could not be completed. Check the message and try again."));
        } finally {
            pending = false;
            dialog.get_primary_btn().prop("disabled", false);
        }
    }
    dialog.set_primary_action(feature.query_label ? __("Find matches") : __("Run review"), run);
    dialog.show();
    if (documentName || seed) run();
}
