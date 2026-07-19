export function createFormContext(event, frm) {
    return {
        type: "form",
        event,

        target: frm,

        doctype: frm.doctype,
        docname: frm.docname,
        doc: frm.doc,
    };
}