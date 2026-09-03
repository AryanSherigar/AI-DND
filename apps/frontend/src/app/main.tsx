import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { logEvent } from "@/shared/lib/logger";
import "../index.css";

window.addEventListener("error", (event) => {
  logEvent("error", "unhandled_frontend_error", {
    message: event.message,
    stack: event.error?.stack,
  });
});

window.addEventListener("unhandledrejection", (event) => {
  logEvent("error", "unhandled_frontend_error", {
    message: String(event.reason),
    stack: event.reason?.stack,
  });
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
