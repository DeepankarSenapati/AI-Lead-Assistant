import ChatDialog from "./dialog";

const ChatAssistant = {
    id: "chat_assistant",

    enabled: true,

    name: "AI Chat Assistant",

    version: "1.0.0",

    description: "Provides AI chat capabilities.",

    author: "Deepankar",

    icon: "comment",

    supports(context) {
        return context.type === "form" ;
    },

    onRefresh(context, api)  {

        api.emit("extension:chat_loaded", {
            doctype: context.doctype,
            docname: context.docname,
        });
        const frm = context.target;

        frm.add_custom_button(
            __("AI Chat Assistant"),
            () => {
                const dialog = new ChatDialog(context);
                dialog.show();
            },
            __("Actions")
        );
    },
};

export default ChatAssistant;