frappe.ui.form.on("Purchase Receipt", {
    refresh(frm) {
        frm.add_custom_button(__("AI Assist"), async () => {

            const file_url = frm.doc.custom_receipt_document;

            if (!file_url) {
                frappe.msgprint({
                    title: __("Document Required"),
                    indicator: "orange",
                    message: __("Please upload a receipt or invoice first."),
                });
                return;
            }

            try {
                const { message } = await frappe.call({
                    method: "ai_lead_assistant.api.process_document",
                    args: {
                        file_url: file_url,
                        doctype: "Purchase Receipt",
                    },
                });

                // Populate normal Purchase Receipt fields
                for (const [fieldname, value] of Object.entries(message)) {

                    if (fieldname === "items") continue;

                    if (value === null || value === undefined || value === "") {
                        continue;
                    }

                    if (!frm.fields_dict[fieldname]) {
                        continue;
                    }

                    // Never overwrite something the user has already entered
                    if (frm.doc[fieldname]) {
                        continue;
                    }

                    await frm.set_value(fieldname, value);
                }

                // Populate Purchase Receipt Item rows
                if (Array.isArray(message.items) && message.items.length > 0) {

                    // Don't overwrite manually entered items
                    if (frm.doc.items && frm.doc.items.length > 0) {
                        frappe.msgprint({
                            title: __("Items Already Entered"),
                            indicator: "orange",
                            message: __(
                                "AI extracted item rows, but existing items were not changed."
                            ),
                        });
                    } else {

                        for (const item of message.items) {

                            const row = frm.add_child("items");

                            if (item.description) {
                                row.description = item.description;
                            }

                            if (item.qty !== null && item.qty !== undefined) {
                                row.qty = item.qty;
                            }

                            if (item.uom) {
                                row.uom = item.uom;
                            }

                            if (item.rate !== null && item.rate !== undefined) {
                                row.rate = item.rate;
                            }
                        }

                        frm.refresh_field("items");
                    }
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
                    message: __(
                        "Unable to extract information from the uploaded receipt or invoice."
                    ),
                });
            }
        });
    },
});