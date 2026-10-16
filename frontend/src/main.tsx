import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource/playfair-display/400.css";
import "@fontsource/playfair-display/500.css";
import "@fontsource/playfair-display/600.css";
import "@fontsource/playfair-display/700.css";
import "@fontsource/playfair-display/500-italic.css";
import "@fontsource-variable/dm-sans";
import "./styles/index.css";
import App from "./App";
import { TripProvider } from "./lib/store";
import { ChatProvider } from "./lib/chat";
import { ToastProvider } from "./components/Toast";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <TripProvider>
          <ChatProvider><App /></ChatProvider>
        </TripProvider>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
);
