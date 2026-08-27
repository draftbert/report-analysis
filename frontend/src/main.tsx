import { createRoot } from "react-dom/client";

import "./assets/styles/tokens.css";
import "./assets/styles/custom.css";

import Application from "./app";

createRoot(document.getElementById("app")!).render(<Application />);
