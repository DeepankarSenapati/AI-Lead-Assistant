export default class Messages {
    constructor(history, state) {
        this.history = history;
        this.state = state;
    }


    addUserMessage(message) {
        this.history.append(`
            <div style="text-align:right; margin-bottom:12px;">
                <span
                    style="
                        background:#0d6efd;
                        color:white;
                        padding:10px 14px;
                        border-radius:12px;
                        display:inline-block;
                        max-width:70%;
                    "
                >
                    ${message}
                </span>
            </div>
        `);

        this.scrollToBottom();
    }

    addBotMessage(message) {
        this.history.append(`
            <div style="margin-bottom:12px;">
                <span
                    style="
                        background:#f1f3f5;
                        padding:10px 14px;
                        border-radius:12px;
                        display:inline-block;
                        max-width:75%;
                    "
                >
                    ${message}
                </span>
            </div>
        `);

        this.scrollToBottom();
    }

    scrollToBottom() {
        this.history.scrollTop(this.history[0].scrollHeight);
    }

    render() {
        this.history.empty();

        this.state.getMessages().forEach((message) => {

            if (message.role === "user") {
                this.addUserMessage(message.content);
            } else {
                this.addBotMessage(message.content);
            }

        });
    }


}