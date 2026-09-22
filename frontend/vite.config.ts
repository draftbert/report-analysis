import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

// Mismo esquema que la plantilla corporativa (alias "@", CSS BEM, tokens --ids-*).
// En desarrollo, /api se redirige al backend (API_URL o localhost:8000).
export default defineConfig({
  plugins: [react()],
  base: "/",
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 3030,
    host: "0.0.0.0",
    proxy: { "/api": { target: process.env.API_URL ?? "http://localhost:8000", changeOrigin: true } },
  },
  build: { outDir: "dist", sourcemap: false, reportCompressedSize: false },
});
