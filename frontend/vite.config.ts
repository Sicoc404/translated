// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  root: ".",
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
    outDir: "dist",
    emptyOutDir: true,
    assetsDir: "assets",
    assetsInlineLimit: 4096,
    sourcemap: true,
  },
  // 确保正确解析路径别名
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
});
