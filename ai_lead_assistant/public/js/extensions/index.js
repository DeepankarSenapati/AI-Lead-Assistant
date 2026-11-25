import registry from "../framework/registry";
import ChatAssistant from "./chat_assistant";
import FormAssistant from "./form_assistant";
import { insightExtension } from "./insight";

export function registerExtensions() {
    registry.register(FormAssistant);
    registry.register(ChatAssistant);
    for (const feature of frappe.boot.ai_insight_features || []) {
        registry.register(insightExtension(feature));
    }
}
