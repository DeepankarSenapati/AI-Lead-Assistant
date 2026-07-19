(() => {
  // ../ai_lead_assistant/ai_lead_assistant/public/js/framework/event_bus.js
  var EventBus = class {
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
      listeners.forEach((callback) => callback(data));
    }
    getListeners() {
      return this.listeners;
    }
  };
  var event_bus_default = new EventBus();

  // ../ai_lead_assistant/ai_lead_assistant/public/js/framework/registry.js
  var Registry = class {
    constructor() {
      this.extensions = [];
      console.log("\u{1F4DA} Registry initialized");
    }
    register(extension) {
      if (!extension.id) {
        throw new Error("Extension must have an id.");
      }
      if (typeof extension.supports !== "function") {
        throw new Error(
          `Extension "${extension.id}" must implement supports().`
        );
      }
      const lifecycleHooks = [
        "onLoad",
        "onRefresh",
        "onSave",
        "onSubmit",
        "onCancel"
      ];
      const hasLifecycleHook = lifecycleHooks.some(
        (hook) => typeof extension[hook] === "function"
      );
      if (!hasLifecycleHook) {
        throw new Error(
          `Extension "${extension.id}" must implement at least one lifecycle hook.`
        );
      }
      this.extensions.push(extension);
      console.log(`\u2795 Registered extension: ${extension.id}`);
      console.log(`\u2705 Registered ${extension.name} v${extension.version}`);
    }
    getExtensions() {
      return this.extensions;
    }
    getExtension(id) {
      return this.extensions.find((e) => e.id === id);
    }
    has(id) {
      return !!this.getExtension(id);
    }
  };
  var registry_default = new Registry();

  // ../ai_lead_assistant/ai_lead_assistant/public/js/framework/api.js
  var FrameworkAPI = class {
    constructor() {
    }
    notify(message) {
      frappe.show_alert({
        message,
        indicator: "green"
      });
    }
    message(title, message) {
      frappe.msgprint({
        title,
        message
      });
    }
    info() {
      console.group("\u{1F680} AI Extension Framework");
      console.log("Version:", "1.0.0");
      console.log("Extensions:", registry_default.getExtensions().length);
      registry_default.getExtensions().forEach((ext) => {
        console.log(
          `\u2714 ${ext.name} (${ext.version})`
        );
      });
      console.groupEnd();
    }
    extensions() {
      return registry_default.getExtensions();
    }
    emit(event, data) {
      event_bus_default.emit(event, data);
    }
    on(event, callback) {
      event_bus_default.on(event, callback);
    }
    events() {
      return event_bus_default.getListeners();
    }
    registry() {
      return registry_default.getExtensions();
    }
    diagnostics() {
      return {
        version: "1.0.0",
        extensions: registry_default.getExtensions(),
        listeners: event_bus_default.getListeners()
      };
    }
  };
  var api_default = new FrameworkAPI();

  // ../ai_lead_assistant/ai_lead_assistant/public/js/framework/extension_manager.js
  var ExtensionManager = class {
    constructor() {
      console.log("\u2705 Extension Manager initialized");
    }
    handle(context) {
      console.log(`\u{1F9E0} Manager received ${context.type}: ${context.doctype}`);
      const extensions = registry_default.getExtensions();
      console.log(`\u{1F4E6} Found ${extensions.length} registered extensions`);
      extensions.forEach((extension) => {
        if (!extension.enabled) {
          console.log(`\u23F8\uFE0F Extension disabled: ${extension.id}`);
          return;
        }
        if (!extension.supports(context)) {
          return;
        }
        if (!extension.__initialized) {
          console.log("Initializing:", extension.id);
          extension.__initialized = true;
          if (extension.onInit) {
            extension.onInit(context, api_default);
          }
        }
        if (context.event === "load" && extension.onLoad) {
          extension.onLoad(context, api_default);
        }
        if (context.event === "refresh" && extension.onRefresh) {
          extension.onRefresh(context, api_default);
        }
      });
    }
  };
  var extension_manager_default = new ExtensionManager();

  // ../ai_lead_assistant/ai_lead_assistant/public/js/framework/context.js
  function createFormContext(event, frm) {
    return {
      type: "form",
      event,
      target: frm,
      doctype: frm.doctype,
      docname: frm.docname,
      doc: frm.doc
    };
  }

  // ../ai_lead_assistant/ai_lead_assistant/public/js/framework/adapters/form_adapter.js
  var FormAdapter = class {
    constructor(manager) {
      this.manager = manager;
      console.log("\u{1F4E1} Form Adapter initialized");
      $(document).on("form-load", (event, frm) => {
        this.handleForm("load", frm);
      });
      $(document).on("form-refresh", (event, frm) => {
        this.handleForm("refresh", frm);
      });
    }
    handleForm(event, frm) {
      console.log("\u{1F4C4} Form detected:", frm.doctype);
      const context = createFormContext(event, frm);
      this.manager.handle(context);
    }
  };
  var form_adapter_default = FormAdapter;

  // ../ai_lead_assistant/ai_lead_assistant/public/js/framework/adapters/index.js
  function registerAdapters(manager) {
    new form_adapter_default(manager);
  }

  // ../ai_lead_assistant/ai_lead_assistant/public/js/extensions/form_assistant/service.js
  function populateForm(context, fields) {
    Object.entries(fields).forEach(([fieldname, value]) => {
      context.target.set_value(fieldname, value);
    });
    frappe.show_alert({
      message: __("Form populated successfully"),
      indicator: "green"
    });
  }
  function analyzeDocument(context, fileUrl, dialog) {
    frappe.call({
      method: "ai_lead_assistant.applications.form_assistant.api.process_document",
      args: {
        doctype: context.doctype,
        file_url: fileUrl
      },
      freeze: true,
      freeze_message: __("Analyzing document..."),
      callback: (r) => {
        console.log("Backend Response:", r.message);
        populateForm(context, r.message);
        dialog.hide();
      },
      error: () => {
        frappe.msgprint({
          title: __("Error"),
          message: __("Failed to analyze the document."),
          indicator: "red"
        });
      }
    });
  }

  // ../ai_lead_assistant/ai_lead_assistant/public/js/extensions/form_assistant/dialog.js
  function openAssistantDialog(context) {
    const dialog = new frappe.ui.Dialog({
      title: __("AI Form Assistant"),
      fields: [
        {
          fieldtype: "Attach",
          fieldname: "document",
          label: __("Document"),
          reqd: 1
        }
      ],
      primary_action_label: __("Analyze"),
      primary_action() {
        const values = dialog.get_values();
        if (!values) {
          return;
        }
        analyzeDocument(
          context,
          values.document,
          dialog
        );
      }
    });
    dialog.show();
  }

  // ../ai_lead_assistant/ai_lead_assistant/public/js/extensions/form_assistant/index.js
  var FormAssistantExtension = {
    id: "form_assistant",
    enabled: true,
    name: "AI Form Assistant",
    version: "1.0.0",
    description: "Provides AI form Autofill capabilities.",
    author: "Deepankar",
    icon: "comment",
    supports(context) {
      return context.type === "form";
    },
    onInit(context, api) {
      console.log("\u2705 Form Assistant onInit");
      api.on("extension:chat_loaded", (data) => {
        console.log("\u{1F4E8} Chat Extension Event:", data);
      });
    },
    onRefresh(context, api) {
      context.target.add_custom_button(
        __("AI Form Assistant"),
        () => {
          openAssistantDialog(context);
        },
        __("Actions")
      );
    }
  };
  var form_assistant_default = FormAssistantExtension;

  // ../ai_lead_assistant/ai_lead_assistant/public/js/extensions/chat_assistant/responses.js
  function getDemoResponse(message, context) {
    const input = message.toLowerCase();
    if (input.includes("hello") || input.includes("hi")) {
      return `
Hello! \u{1F44B}

Welcome to the ${context.doctype} assistant.

I'm currently a demonstration of the AI Extension Framework.

This extension doesn't use an LLM yet, but it shows how another AI application can plug into the framework.
`;
    }
    if (input.includes("help")) {
      return `
Eventually I could help you with:

\u2022 ERPNext workflows
\u2022 Company documentation
\u2022 Business knowledge
\u2022 AI Copilot
\u2022 Enterprise search

Right now I'm only a demo running on top of the AI Extension Framework.
`;
    }
    if (input.includes("where") || input.includes("page") || input.includes("screen")) {
      return `
You're currently viewing the ${context.doctype} DocType.

This information comes directly from the ERPNext form context passed into the extension.
`;
    }
    if (input.includes(context.doctype.toLowerCase())) {
      return `
You're asking about the current ${context.doctype} page.

In the future this assistant could answer questions using ERP data or enterprise knowledge.
`;
    }
    if (input.includes("document") || input.includes("record")) {
      return `
    You're currently working on:

    ${context.doctype}

    Document Name:

    ${context.docname}

    The AI Extension Framework automatically passed this information into the Chat Assistant.
    `;
    }
    return `
That's an interesting question.

I'm currently a demonstration chatbot running on the AI Extension Framework.

In future versions I could connect to:

\u2022 OpenAI
\u2022 Company Knowledge Base
\u2022 ERP Data
\u2022 Workflows

without requiring any changes to the framework.
`;
  }

  // ../ai_lead_assistant/ai_lead_assistant/public/js/extensions/chat_assistant/render.js
  var ChatRenderer = class {
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
  };

  // ../ai_lead_assistant/ai_lead_assistant/public/js/extensions/chat_assistant/components/messages.js
  var Messages = class {
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
  };

  // ../ai_lead_assistant/ai_lead_assistant/public/js/extensions/chat_assistant/components/composer.js
  var Composer = class {
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
      if (!message)
        return;
      this.input.val("");
      this.onSend(message);
    }
  };

  // ../ai_lead_assistant/ai_lead_assistant/public/js/extensions/chat_assistant/state.js
  var ChatState = class {
    constructor() {
      this.messages = [];
    }
    add(role, content) {
      this.messages.push({
        id: Date.now() + Math.random(),
        role,
        content,
        timestamp: new Date()
      });
    }
    getMessages() {
      return this.messages;
    }
    clear() {
      this.messages = [];
    }
  };

  // ../ai_lead_assistant/ai_lead_assistant/public/js/extensions/chat_assistant/dialog.js
  var ChatDialog = class {
    constructor(context) {
      this.context = context;
      this.dialog = null;
      this.history = null;
      this.input = null;
      this.state = new ChatState();
    }
    show() {
      this.dialog = new frappe.ui.Dialog({
        title: "\u{1F916} AI Chat Assistant",
        size: "large",
        fields: [
          {
            fieldtype: "HTML",
            fieldname: "chat_ui"
          }
        ]
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
        Hello! \u{1F44B}<br><br>
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
  };

  // ../ai_lead_assistant/ai_lead_assistant/public/js/extensions/chat_assistant/index.js
  var ChatAssistant = {
    id: "chat_assistant",
    enabled: true,
    name: "AI Chat Assistant",
    version: "1.0.0",
    description: "Provides AI chat capabilities.",
    author: "Deepankar",
    icon: "comment",
    supports(context) {
      return context.type === "form";
    },
    onRefresh(context, api) {
      api.emit("extension:chat_loaded", {
        doctype: context.doctype,
        docname: context.docname
      });
      const frm = context.target;
      frm.add_custom_button(
        __("AI Chat Assistant"),
        () => {
          const dialog = new ChatDialog(context);
          dialog.show();
        },
        __("Actions")
      );
    }
  };
  var chat_assistant_default = ChatAssistant;

  // ../ai_lead_assistant/ai_lead_assistant/public/js/extensions/index.js
  function registerExtensions() {
    registry_default.register(form_assistant_default);
    console.log("Registering Form Assistant");
    registry_default.register(chat_assistant_default);
    console.log("Registering Chat Assistant");
  }

  // ../ai_lead_assistant/ai_lead_assistant/public/js/framework/bootstrap.js
  console.log("\u{1F680} AI Extension Framework Bootstrapped");
  window.AIFramework = api_default;
  registerExtensions();
  registerAdapters(extension_manager_default);
})();
//# sourceMappingURL=ai_lead_assistant.bundle.2GY5E66Q.js.map
