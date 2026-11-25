import { openAssistantDialog } from "./dialog";

export default {
    id: "form_assistant",
    name: "AI Form Assistant",
    version: "1.0.0",
    enabled: true,
    supports: context => context.type === "form",

    onRefresh(context) {
        if (!context.target.custom_buttons[__(this.name)]) {
            context.target.add_custom_button(__(this.name), () => openAssistantDialog(context), __("Actions"));
        }
    },

    onDisable(context) {
        if (context.target.custom_buttons[__(this.name)]) {
            context.target.remove_custom_button(__(this.name), __("Actions"));
        }
    },
};
