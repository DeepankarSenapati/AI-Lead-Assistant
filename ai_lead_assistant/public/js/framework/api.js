import events from "./event_bus";
import registry from "./registry";

class FrameworkAPI {

    constructor() {
        
    }

    notify(message) {
        frappe.show_alert({
            message,
            indicator: "green"
        });
    }

    message(title, message) {
        frappe.msgprint({
            title,
            message
        });
    }

    info() {

        console.group("🚀 AI Extension Framework");

        console.log("Version:", "1.0.0");

        console.log("Extensions:", registry.getExtensions().length);

        registry.getExtensions().forEach((ext) => {
            console.log(
                `✔ ${ext.name} (${ext.version})`
            );
        });

        console.groupEnd();

    }

    extensions() {
        return registry.getExtensions();
    }

    emit(event, data) {
        events.emit(event, data);
    }

    on(event, callback) {
        events.on(event, callback);
    }

    events() {
        return events.getListeners();
    }

    registry() {
        return registry.getExtensions();
    }

    diagnostics() {

        return {
            version: "1.0.0",
            extensions: registry.getExtensions(),
            listeners: events.getListeners()
        };

    }

}

export default new FrameworkAPI();