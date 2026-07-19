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
            },
        ],

        primary_action_label: __("Analyze"),

        primary_action() {
            const values = dialog.get_values();

            if (!values) {
                return;
            }

            analyzeDocument(
                context,
                values.document,
                dialog
            );
        }
    });

    dialog.show();
}