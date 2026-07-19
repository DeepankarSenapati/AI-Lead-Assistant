export function getDemoResponse(message, context) {
    const input = message.toLowerCase();

    // Greeting
    if (input.includes("hello") || input.includes("hi")) {
        return `
Hello! 👋

Welcome to the ${context.doctype} assistant.

I'm currently a demonstration of the AI Extension Framework.

This extension doesn't use an LLM yet, but it shows how another AI application can plug into the framework.
`;
    }

    // Help
    if (input.includes("help")) {
        return `
Eventually I could help you with:

• ERPNext workflows
• Company documentation
• Business knowledge
• AI Copilot
• Enterprise search

Right now I'm only a demo running on top of the AI Extension Framework.
`;
    }

    // Current page
    if (
        input.includes("where") ||
        input.includes("page") ||
        input.includes("screen")
    ) {
        return `
You're currently viewing the ${context.doctype} DocType.

This information comes directly from the ERPNext form context passed into the extension.
`;
    }

    // Lead / Employee / Customer etc.
    if (input.includes(context.doctype.toLowerCase())) {
        return `
You're asking about the current ${context.doctype} page.

In the future this assistant could answer questions using ERP data or enterprise knowledge.
`;
    }


    if (
        input.includes("document") ||
        input.includes("record")
    ) {

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

• OpenAI
• Company Knowledge Base
• ERP Data
• Workflows

without requiring any changes to the framework.
`;
}