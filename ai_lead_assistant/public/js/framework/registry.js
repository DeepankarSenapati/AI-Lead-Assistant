class Registry {
    constructor() {
        this.extensions = [];

        console.log("📚 Registry initialized");
    }

    register(extension) {
        if (!extension.id) {
            throw new Error("Extension must have an id.");
        }

        if (typeof extension.supports !== "function") {
            throw new Error(
                `Extension "${extension.id}" must implement supports().`
            );
        }

        const lifecycleHooks = [
            "onLoad",
            "onRefresh",
            "onSave",
            "onSubmit",
            "onCancel",
        ];

        const hasLifecycleHook = lifecycleHooks.some(
            (hook) => typeof extension[hook] === "function"
        );

        if (!hasLifecycleHook) {
            throw new Error(
                `Extension "${extension.id}" must implement at least one lifecycle hook.`
            );
        }

        this.extensions.push(extension);

        console.log(`➕ Registered extension: ${extension.id}`);
        console.log(`✅ Registered ${extension.name} v${extension.version}`);
    }
    getExtensions() {
        return this.extensions;
    }

    getExtension(id) {
        return this.extensions.find(e => e.id === id);
    }

    has(id) {
        return !!this.getExtension(id);
    }
}

export default new Registry();