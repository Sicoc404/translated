// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
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
    chunkSizeWarningLimit: 1000, // 增加警告阈值到1000kB
  }
});
