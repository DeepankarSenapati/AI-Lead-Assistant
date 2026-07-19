export default class Composer {
    constructor(wrapper, onSend) {
        this.wrapper = wrapper;
        this.onSend = onSend;

        this.input = wrapper.find("#ai-chat-input");
        this.button = wrapper.find("#ai-chat-send");
    }

    initialize() {
        this.button.on("click", () => this.send());

        this.input.on("keypress", (e) => {
            if (e.which === 13) {
                this.send();
            }
        });
    }

    send() {
        const message = this.input.val().trim();

        if (!message) return;

        this.input.val("");

        this.onSend(message);
    }
}