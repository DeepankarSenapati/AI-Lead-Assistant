// Socket.IO covers colleagues on other devices. Storage events also reach other
// Desk tabs on this origin when a local site's websocket is unavailable.
const storageKey = "ai_lead_assistant:assignment_change";
const notify = frappe.utils.debounce(() => $(document).trigger("ai-feature-assignments-refresh"), 100);

$(document).on("ai-feature-assignment-updated", () => {
    try {
        localStorage.setItem(storageKey, String(Date.now()) + Math.random());
    } catch {
        // Private browsing may disallow storage.
    }
    notify();
});
window.addEventListener("storage", event => { if (event.key === storageKey) notify(); });
window.addEventListener("focus", notify);
document.addEventListener("visibilitychange", () => { if (!document.hidden) notify(); });
$(document).on("app_ready", () => {
    frappe.realtime.on("ai_feature_assignment_changed", notify);
    frappe.realtime.on("connect", notify);
});
