import api from "./api";
import registry from "./registry";

class ExtensionManager {
    constructor() {
        this.initialized = new Set();
    }

    handle(context, allowed) {
        const hook = context.event === "load" ? "onLoad" : "onRefresh";
        for (const extension of registry.getExtensions()) {
            if (!extension.enabled || !allowed.includes(extension.id) || !extension.supports(context)) {
                if (context.event === "refresh") extension.onDisable?.(context, api);
                continue;
            }
            if (!this.initialized.has(extension.id)) {
                extension.onInit?.(context, api);
                this.initialized.add(extension.id);
            }
            extension[hook]?.(context, api);
        }
    }
}

export default new ExtensionManager();
