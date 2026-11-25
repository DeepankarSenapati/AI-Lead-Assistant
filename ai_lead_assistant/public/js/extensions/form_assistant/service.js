const hasValue = value => value !== null && value !== undefined && value !== "";

export async function analyzeDocument(context, fileUrl, dialog) {
    const frm = context.target;
    const args = { doctype: context.doctype, file_url: fileUrl };
    if (!frm.is_new()) args.document_name = context.docname;
    const { message: fields } = await frappe.call({
        method: "ai_lead_assistant.api.process_document",
        args,
        freeze: true,
        freeze_message: __("Analyzing document…"),
    });
    if (frm.doc !== context.doc) return;
    for (const [key, value] of Object.entries(fields || {})) {
        if (key === "items" || !frm.fields_dict[key] || !hasValue(value) || hasValue(frm.doc[key])) continue;
        await frm.set_value(key, value);
    }
    if (Array.isArray(fields?.items) && fields.items.length && frm.fields_dict.items) {
        if (frm.doc.items?.length) {
            frappe.msgprint(__("AI extracted item rows. Your existing items were kept."));
        } else {
            for (const item of fields.items) {
                const row = frm.add_child("items");
                for (const key of ["description", "qty", "uom", "rate"]) {
                    if (hasValue(item[key])) row[key] = item[key];
                }
            }
            frm.refresh_field("items");
        }
    }
    dialog.hide();
    frappe.show_alert({ message: __("AI extraction completed"), indicator: "green" });
}
