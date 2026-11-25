import { analyzeDocument } from "./service";

export function openAssistantDialog(context) {
    const dialog = new frappe.ui.Dialog({
        title: __("AI Form Assistant"),

        fields: [
            {
                fieldtype: "Attach",
                fieldname: "document",
                label: __("Document"),
                reqd: 1,
                default: context.doc.custom_id_document_ || context.doc.custom_receipt_document,
            },
        ],

        primary_action_label: __("Analyze"),

        primary_action() {
            const values = dialog.get_values();

            if (!values) {
                return;
            }

            return analyzeDocument(
                context,
                values.document,
                dialog
            );
        }
    });

    dialog.show();
}
