export default class ChatState {
    constructor() {
        this.messages = [];
    }

    add(role, content) {
        this.messages.push({
            id: Date.now() + Math.random(),
            role,
            content,
            timestamp: new Date(),
        });
    }

    getMessages() {
        return this.messages;
    }

    clear() {
        this.messages = [];
    }
}