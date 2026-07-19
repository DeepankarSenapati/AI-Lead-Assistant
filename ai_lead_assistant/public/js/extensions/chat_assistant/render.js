export default class ChatRenderer {
    constructor(wrapper, context) {
        this.wrapper = wrapper;
        this.context = context;
    }

    render() {
        this.wrapper.html(`
            <div style="display:flex; flex-direction:column; height:500px;">

                <!-- Header -->
                <div style="
                    padding:15px;
                    border-bottom:1px solid #ddd;
                    background:#f8f9fa;
                ">
                    <h4 style="margin:0;">
                        Welcome to the <b>${this.context.doctype}</b> module
                    </h4>

                    <div style="
                        color:#666;
                        margin-top:5px;
                    ">
                        You're currently viewing <b>${this.context.docname || "New Document"}</b>
                    </div>
                </div>

                <!-- Chat History -->
                <div
                    id="ai-chat-history"
                    style="
                        flex:1;
                        overflow-y:auto;
                        padding:15px;
                        background:white;
                    "
                >
                </div>

                <!-- Input -->
                <div style="
                    border-top:1px solid #ddd;
                    padding:12px;
                    display:flex;
                    gap:10px;
                ">
                    <input
                        id="ai-chat-input"
                        type="text"
                        placeholder="Type your message..."
                        style="
                            flex:1;
                            padding:10px;
                            border:1px solid #ccc;
                            border-radius:6px;
                        "
                    />

                    <button
                        id="ai-chat-send"
                        class="btn btn-primary"
                    >
                        Send
                    </button>

                </div>

            </div>
        `);
    }
}