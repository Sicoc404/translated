// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  root: resolve(__dirname, "frontend"),
  server: {
    host: true,  // 绑定到 0.0.0.0
    port: Number(process.env.PORT) || 5173,
    strictPort: true,
  },
  preview: {
    host: true,
    port: Number(process.env.PORT) || 5173,
    strictPort: true,
  },
  build: {
    outDir: resolve(__dirname, "dist"),
    emptyOutDir: true
  }
}); 