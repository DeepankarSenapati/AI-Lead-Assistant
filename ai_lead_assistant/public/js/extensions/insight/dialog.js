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
    if (feature.needs_saved && frm.is_new()) {
        frappe.msgprint(__("Save the new document, then open {0} to review it.", [__(feature.label)]));
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
    if (feature.needs_saved && frm.is_dirty()) {
        fields.push({ fieldtype: "HTML", fieldname: "saved_notice" });
    }
    fields.push({ fieldtype: "HTML", fieldname: "results" });
    const dialog = new frappe.ui.Dialog({ title: __(feature.label), fields, size: "large" });
    if (dialog.fields_dict.saved_notice) {
        $("<p>", { class: "text-muted" }).text(__("Reviewing the saved version. Save the form to include your latest edits."))
            .appendTo(dialog.fields_dict.saved_notice.$wrapper);
    }
    const root = dialog.fields_dict.results.$wrapper.attr("aria-live", "polite");
    let pending = false;

    async function run(values = {}) {
        if (pending) return;
        if (frm.doc !== doc) {
            dialog.hide();
            frappe.msgprint(__("The form has changed. Open the assistant again to review the current record."));
            return;
        }
        // Frappe captures the submitted input before refreshing a required dialog field.
        const query = feature.query_label ? (values.query ?? dialog.get_value("query") ?? "").trim() : "";
        if (query.length > 500) {
            frappe.msgprint(__("Use a search of 500 characters or fewer."));
            return;
        }
        pending = true;
        dialog.get_primary_btn().prop("disabled", true);
        root.empty().text(__("Checking ERPNext records…"));
        try {
            if (values.query && dialog.get_value("query") !== values.query) {
                await dialog.set_value("query", values.query);
            }
            const { message } = await frappe.call({
                method: "ai_lead_assistant.framework.insights.run",
                args: { feature: feature.id, doctype: frm.doctype, document_name: documentName, query },
            });
            showFindings(root, message);
            if (message.can_draft && feature.draft_method) {
                const draftButton = $("<button>", { type: "button", class: "btn btn-default btn-sm" })
                    .text(__(feature.draft_label || "Draft handoff with OpenAI")).appendTo(root);
                $("<small>", { class: "d-block text-muted mt-1" })
                    .text(__(feature.draft_notice || "Sends the displayed sales context, task details and note excerpts to your configured OpenAI account."))
                    .appendTo(root);
                const draftArea = $("<div>", { "aria-live": "polite" }).prependTo(root);
                draftButton.on("click", async () => {
                    if (pending) return;
                    pending = true;
                    draftButton.prop("disabled", true);
                    dialog.get_primary_btn().prop("disabled", true);
                    try {
                        const { message: draft } = await frappe.call({
                            method: feature.draft_method, args: { doctype: frm.doctype, document_name: documentName, version: message.version },
                        });
                        const block = $("<section>", { class: "border rounded p-3 mb-3" }).appendTo(draftArea.empty());
                        $("<strong>").text(__("AI draft")).appendTo(block);
                        $("<p>", { class: "mt-2 mb-0" }).css("white-space", "pre-wrap").text(draft.text).appendTo(block);
                    } catch (error) {
                        draftArea.text(__("The AI draft could not be created. Your local brief is available below."));
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
