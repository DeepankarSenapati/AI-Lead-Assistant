frappe.ui.form.on("Lead", {
    refresh(frm) {
        frm.add_custom_button(__("AI Assist"), async () => {

            const file_url = frm.doc.custom_id_document_;

            if (!file_url) {
                frappe.msgprint({
                    title: __("Document Required"),
                    indicator: "orange",
                    message: __("Please upload an ID Document first."),
                });
                return;
            }

            try {
                const { message } = await frappe.call({
                    method: "ai_lead_assistant.api.process_document",
                    args: {
                        file_url: file_url,
                        doctype: "Lead",
                    },
                });

                for (const [fieldname, value] of Object.entries(message)) {

                    if (!value) continue;

                    if (!frm.fields_dict[fieldname]) continue;

                    if (frm.doc[fieldname]) continue;

                    await frm.set_value(fieldname, value);
                }

                frm.refresh_fields();

                frappe.show_alert({
                    message: __("AI extraction completed"),
                    indicator: "green",
                });

            } catch (error) {
                console.error(error);

                frappe.msgprint({
                    title: __("AI Extraction Failed"),
                    indicator: "red",
                    message: __("Unable to extract information from the uploaded document."),
                });
            }
        });
    },
});