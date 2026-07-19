import registry from "../framework/registry";

import FormAssistantExtension from "./form_assistant";
import ChatAssistant from "./chat_assistant";

export function registerExtensions() {
    registry.register(FormAssistantExtension);
    console.log("Registering Form Assistant");

    registry.register(ChatAssistant);
    console.log("Registering Chat Assistant");
}