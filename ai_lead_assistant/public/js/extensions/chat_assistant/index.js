import ChatDialog from "./dialog";

export default {
    id: "chat_assistant",
    name: "AI Chat Assistant",
    version: "1.0.0",
    enabled: true,
    supports: context => context.type === "form",

    onRefresh(context, api) {
        if (!context.target.custom_buttons[__(this.name)]) {
            context.target.add_custom_button(__(this.name), () => new ChatDialog(context).show(), __("Actions"));
            api.emit("extension:chat_loaded", { doctype: context.doctype, docname: context.docname });
        }
    },

    onDisable(context) {
        if (context.target.custom_buttons[__(this.name)]) {
            context.target.remove_custom_button(__(this.name), __("Actions"));
        }
    },
};
