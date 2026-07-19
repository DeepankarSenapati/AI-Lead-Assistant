export function populateForm(context, fields) {
    Object.entries(fields).forEach(([fieldname, value]) => {
        context.target.set_value(fieldname, value);
    });

    frappe.show_alert({
        message: __("Form populated successfully"),
        indicator: "green",
    });
}

export function analyzeDocument(context, fileUrl, dialog) {
    frappe.call({
        method: "ai_lead_assistant.applications.form_assistant.api.process_document",

        args: {
            doctype: context.doctype,
            file_url: fileUrl,
        },

        freeze: true,
        freeze_message: __("Analyzing document..."),

        callback: (r) => {
            console.log("Backend Response:", r.message);
            populateForm(context, r.message);

            dialog.hide();
        },

        error: () => {
            frappe.msgprint({
                title: __("Error"),
                message: __("Failed to analyze the document."),
                indicator: "red",
            });
        },
    });
}