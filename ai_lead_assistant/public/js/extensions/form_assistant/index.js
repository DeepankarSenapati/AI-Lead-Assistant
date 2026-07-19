import { openAssistantDialog } from "./dialog";

const FormAssistantExtension = {
    id: "form_assistant",

    enabled: true,

    name: "AI Form Assistant",

    version: "1.0.0",

    description: "Provides AI form Autofill capabilities.",

    author: "Deepankar",

    icon: "comment",

    supports(context) {
        return context.type === "form"   ;
    },

    onInit(context, api) {

        console.log("✅ Form Assistant onInit");

        api.on("extension:chat_loaded", (data) => {
            console.log("📨 Chat Extension Event:", data);
        });

    },

    onRefresh(context, api) {

        
        context.target.add_custom_button(
            __("AI Form Assistant"),
            () => {
                openAssistantDialog(context);
            },
            __("Actions")
        );
    },
};

export default FormAssistantExtension;