import FormAdapter from "./form_adapter";

export function registerAdapters(manager) {
    new FormAdapter(manager);
}