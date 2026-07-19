import { getDemoResponse } from "./responses";
import ChatRenderer from "./render";
import Messages from "./components/messages";
import Composer from "./components/composer";
import ChatState from "./state";

export default class ChatDialog {
    constructor(context) {
        this.context = context;
        this.dialog = null;
        this.history = null;
        this.input = null;
        this.state = new ChatState();
    }

    show() {
        this.dialog = new frappe.ui.Dialog({
            title: "🤖 AI Chat Assistant",
            size: "large",
            fields: [
                {
                    fieldtype: "HTML",
                    fieldname: "chat_ui",
                },
            ],
        });

        const wrapper = this.dialog.fields_dict.chat_ui.$wrapper;

        const renderer = new ChatRenderer(wrapper, this.context);
        renderer.render();

        this.history = wrapper.find("#ai-chat-history");

        this.messages = new Messages(
            this.history,
            this.state
        );

        this.input = wrapper.find("#ai-chat-input");

        const greeting = `
        Hello! 👋<br><br>
        I'm currently a demo chatbot running on the AI Extension Framework.<br><br>
        Eventually I can connect to OpenAI, ERP data, enterprise knowledge bases, workflows and much more.<br><br>
        How can I help you today?
        `;

        this.state.add("assistant", greeting);
        this.messages.render();

        this.composer = new Composer(
            wrapper,
            (message) => this.sendMessage(message)
        );

        this.composer.initialize();
        this.dialog.show();
    }

    sendMessage(message) {
        this.state.add("user", message);
        this.messages.render();

        setTimeout(() => {
            const response = getDemoResponse(
                message,
                this.context
            );

            this.state.add("assistant", response);
            this.messages.render();
        }, 400);
    }
        
}