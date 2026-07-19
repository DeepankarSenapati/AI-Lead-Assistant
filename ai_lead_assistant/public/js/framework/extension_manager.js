import api from "./api";
import registry from "./registry";

class ExtensionManager {
    constructor() {
        console.log("✅ Extension Manager initialized");
    }

    handle(context) {
        console.log(`🧠 Manager received ${context.type}: ${context.doctype}`);

        const extensions = registry.getExtensions();

        console.log(`📦 Found ${extensions.length} registered extensions`);

        extensions.forEach((extension) => {

            if (!extension.enabled) {
                console.log(`⏸️ Extension disabled: ${extension.id}`);
                return;
            }

            if (!extension.supports(context)) {
                return;
            }

            // Run only once
            if (!extension.__initialized) {

                console.log("Initializing:", extension.id);

                extension.__initialized = true;

                if (extension.onInit) {
                    extension.onInit(context, api);
                }

            }

            if (context.event === "load" && extension.onLoad) {
                extension.onLoad(context, api);
            }

            if (context.event === "refresh" && extension.onRefresh) {
                extension.onRefresh(context, api);
            }

        });
    }
}
export default new ExtensionManager();