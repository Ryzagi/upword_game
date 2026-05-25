import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { applySettingsToDom, useSettingsStore } from "./stores/useSettingsStore";
import "./styles/tailwind.css";
import "./i18n";

// Reflect persisted user preferences onto <html> as early as possible so the
// first paint already respects theme + font size + a11y choices.
applySettingsToDom(useSettingsStore.getState());
useSettingsStore.subscribe((s) => applySettingsToDom(s));

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
