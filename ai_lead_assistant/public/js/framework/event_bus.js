class EventBus {

    constructor() {
        this.listeners = {};
    }

    on(event, callback) {

        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }

        this.listeners[event].push(callback);
    }

    emit(event, data) {

        const listeners = this.listeners[event] || [];

        listeners.forEach(callback => callback(data));
    }

    getListeners() {
        return this.listeners;
    }

}

export default new EventBus();