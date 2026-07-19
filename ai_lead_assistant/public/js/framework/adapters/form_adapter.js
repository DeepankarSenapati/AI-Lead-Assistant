import { createFormContext } from "../context";

class FormAdapter {
    constructor(manager) {
        this.manager = manager;

        console.log("📡 Form Adapter initialized");

        $(document).on("form-load", (event, frm) => {
            this.handleForm("load", frm);
        });

        $(document).on("form-refresh", (event, frm) => {
            this.handleForm("refresh", frm);
        });
    }

    handleForm(event, frm) {
        console.log("📄 Form detected:", frm.doctype);

        const context = createFormContext(event, frm);

        this.manager.handle(context);
            }
        }

export default FormAdapter;