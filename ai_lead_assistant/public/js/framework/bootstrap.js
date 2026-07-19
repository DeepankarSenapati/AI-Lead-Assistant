import manager from "./extension_manager";
import api from "./api";

import { registerAdapters } from "./adapters";
import { registerExtensions } from "../extensions";

console.log("🚀 AI Extension Framework Bootstrapped");
window.AIFramework = api;

registerExtensions();
registerAdapters(manager);