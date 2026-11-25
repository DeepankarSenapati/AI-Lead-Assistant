import { openInsight } from "./dialog";

export function insightExtension(feature) {
    return {
        id: feature.id,
        name: feature.label,
        version: "1.0.0",
        enabled: true,
        supports: context => context.type === "form" && feature.forms.includes(context.doctype),
        onRefresh({ target: frm }) {
            const label = __(feature.label);
            if (!frm.custom_buttons[label]) {
                frm.add_custom_button(label, () => openInsight(feature, frm), __("Actions"));
            }
        },
        onDisable({ target: frm }) {
            const label = __(feature.label);
            if (frm.custom_buttons[label]) frm.remove_custom_button(label, __("Actions"));
        },
    };
}
