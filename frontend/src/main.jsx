import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import { watchGlobalErrors } from "./utils/reportError";
import "./index.css";

watchGlobalErrors();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
