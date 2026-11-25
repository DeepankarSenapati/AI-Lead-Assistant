frappe.pages["ai-feature-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({ parent: wrapper, title: __("AI Feature Dashboard"), single_column: true });
    wrapper.dashboard = new FeatureDashboard(page);
};

frappe.pages["ai-feature-dashboard"].on_page_show = wrapper => wrapper.dashboard.load();

class FeatureDashboard {
    constructor(page) {
        this.root = $('<div class="ai-assignment-dashboard">').appendTo(page.main);
        this.root.html(`
            <section aria-label="${__("AI features")}">
                <h2>${__("Features")}</h2><div class="ai-catalog"></div>
            </section>
            <div class="ai-assignment-layout">
                <nav aria-label="${__("ERPNext modules")}">
                    <h2>${__("Modules")}</h2>
                    <input type="search" class="form-control ai-module-search" aria-label="${__("Find a module")}" placeholder="${__("Find a module")}">
                    <div class="ai-modules"></div>
                </nav>
                <section class="ai-targets" aria-label="${__("Feature assignments")}">
                    <div class="ai-module-heading"></div>
                    <input type="search" class="form-control ai-form-search" aria-label="${__("Find a form")}" placeholder="${__("Find a form")}">
                    <div class="ai-forms"></div>
                </section>
            </div>
            <div class="ai-feedback text-muted" role="status"></div>
        `);
        this.root.on("click", "[data-feature]", event => {
            this.featureId = event.currentTarget.dataset.feature;
            this.render();
        });
        this.root.on("click", "[data-module]", event => {
            this.module = event.currentTarget.dataset.module;
            this.root.find(".ai-form-search").val("");
            this.render();
        });
        this.root.on("input", ".ai-module-search", () => this.renderModules());
        this.root.on("input", ".ai-form-search", () => this.renderForms());
        this.root.on("click", "[data-state]", event => this.save(event.currentTarget));
        this.root.on("click", ".ai-retry", () => this.load());
    }

    async load() {
        const request = this.request = {};
        if (!this.data) this.status(__("Loading assignments…"));
        try {
            const { message } = await frappe.call("ai_lead_assistant.framework.assignments.get_dashboard");
            if (request !== this.request) return;
            this.data = message;
            this.modules = [...new Set(message.forms.map(row => row.module))];
            this.featureId ||= message.features[0]?.id;
            this.module ||= this.modules.includes("CRM") ? "CRM" : this.modules[0];
            this.status("");
            this.render();
        } catch (error) {
            if (request !== this.request) return;
            this.status(__("Could not load assignments."));
            $("<button>", { type: "button", class: "btn btn-default btn-xs ai-retry", text: __("Retry") })
                .appendTo(this.root.find(".ai-feedback"));
        }
    }

    get feature() { return this.data.features.find(item => item.id === this.featureId); }
    moduleLabel(name) { return name === "Accounts" ? __("Accounting") : __(name); }
    supports(name) { return this.feature.forms === null || this.feature.forms.includes(name); }
    rule(type, name) {
        return this.data.rules.find(row => row.feature === this.featureId && row.target_type === type && row.target === name);
    }
    get moduleEnabled() {
        const rule = this.rule("Module Def", this.module);
        return rule ? Boolean(rule.enabled) : this.feature.default_enabled;
    }
    status(message) { this.root.find(".ai-feedback").text(message); }

    render() {
        const cards = this.root.find(".ai-catalog").empty();
        for (const feature of this.data.features) {
            const button = $("<button>", { type: "button", class: "ai-feature-card", "data-feature": feature.id,
                "aria-pressed": String(feature.id === this.featureId) }).appendTo(cards);
            $("<span>", { class: "ai-feature-icon", "aria-hidden": "true" })
                .html(frappe.utils.icon(feature.icon, "md")).appendTo(button);
            const text = $("<span>").appendTo(button);
            $("<strong>").text(__(feature.label)).appendTo(text);
            $("<small>").text(__(feature.description)).appendTo(text);
        }
        this.renderModules();
        const heading = this.root.find(".ai-module-heading").empty();
        const search = this.root.find(".ai-form-search");
        if (!this.module || !this.feature) {
            heading.text(__("No ERPNext forms available."));
            search.hide();
            this.root.find(".ai-forms").empty();
            return;
        }
        search.show();
        const rows = this.data.forms.filter(row => row.module === this.module);
        const count = rows.filter(row => this.supports(row.name)).length;
        const line = $("<div>", { class: "ai-section-line" }).appendTo(heading);
        $("<h2>").text(this.moduleLabel(this.module)).appendTo(line);
        $("<span>", { class: "ai-coverage" }).text(__("{0} of {1} forms compatible", [count, rows.length])).appendTo(line);
        const group = $("<div>", { class: "ai-default" }).appendTo(heading);
        const copy = $("<div>").appendTo(group);
        $("<strong>").text(__("Module default")).appendTo(copy);
        $("<small>").text(count ? __("Applies to compatible forms unless a form has its own setting.") :
            __("This feature has no compatible forms in this module.")).appendTo(copy);
        this.toggle(group, "Module Def", this.module, this.moduleEnabled && count > 0, !count);
        this.renderForms();
    }

    renderModules() {
        if (!this.data) return;
        const term = this.root.find(".ai-module-search").val().trim().toLowerCase();
        const list = this.root.find(".ai-modules").empty();
        for (const name of this.modules) {
            if (!(name + " " + this.moduleLabel(name)).toLowerCase().includes(term)) continue;
            $("<button>", { type: "button", "data-module": name, "aria-pressed": String(name === this.module) })
                .text(this.moduleLabel(name)).appendTo(list);
        }
        if (!list.children().length) list.text(__("No matching modules."));
    }

    renderForms() {
        if (!this.module || !this.data) return;
        const term = this.root.find(".ai-form-search").val().trim().toLowerCase();
        const list = this.root.find(".ai-forms").empty();
        const forms = this.data.forms.filter(row => row.module === this.module && __(row.name).toLowerCase().includes(term));
        for (const { name } of forms) {
            const compatible = this.supports(name);
            const rule = this.rule("DocType", name);
            const active = compatible && (rule ? Boolean(rule.enabled) : this.moduleEnabled);
            const row = $("<div>", { class: "ai-form-row" }).appendTo(list);
            const copy = $("<div>", { class: "ai-row-copy" }).appendTo(row);
            $("<strong>").text(__(name)).appendTo(copy);
            const reason = compatible ? (rule ? __("Form override") : __("Uses module default")) : __(this.feature.reason);
            $("<small>", { class: compatible ? "" : "ai-warning" }).text(reason).appendTo(copy);
            if (compatible && rule) {
                $("<button>", { type: "button", class: "btn btn-link btn-xs ai-reset", "data-state": "inherit",
                    "data-type": "DocType", "data-target": name, "aria-label": __("Use module default for {0}", [__(name)]) })
                    .text(__("Use default")).appendTo(row);
            }
            this.toggle(row, "DocType", name, active, !compatible);
        }
        if (!forms.length) list.text(__("No matching forms."));
    }

    toggle(parent, type, name, active, unavailable) {
        $("<button>", { type: "button", class: "ai-toggle", role: "switch", disabled: unavailable || this.saving,
            "aria-checked": String(active), "aria-label": __("{0} on {1}", [__(this.feature.label), __(name)]),
            title: unavailable ? __("Incompatible assignment") : (active ? __("Turn off") : __("Turn on")),
            "data-state": active ? "off" : "on", "data-type": type, "data-target": name })
            .append($("<span>", { class: "ai-switch-track", "aria-hidden": "true" }))
            .append(document.createTextNode(unavailable ? __("Unavailable") : active ? __("On") : __("Off"))).appendTo(parent);
    }

    async save(button) {
        if (this.saving) return;
        const { type, target, state } = button.dataset;
        const feature = this.featureId;
        this.saving = true;
        this.root.attr("aria-busy", "true").find("[data-state]").prop("disabled", true);
        try {
            await frappe.call({ method: "ai_lead_assistant.framework.assignments.set_assignment",
                args: { feature, target_type: type, target, state } });
            $(document).trigger("ai-feature-assignment-updated");
            frappe.show_alert({ message: __("Assignment saved"), indicator: "green" });
        } finally {
            this.saving = false;
            await this.load();
            this.root.removeAttr("aria-busy");
            const controls = this.root.find("[data-state]").toArray();
            controls.find(el => el.dataset.type === type && el.dataset.target === target && !el.disabled)?.focus();
        }
    }
}
