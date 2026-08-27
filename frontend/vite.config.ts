import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

// Mismo esquema que la plantilla corporativa (alias "@", CSS BEM, tokens --ids-*).
// En el entorno corporativo se sustituye tokens.css por @inditex/sewingiopdsweb-styles.
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
