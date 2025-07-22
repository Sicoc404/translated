// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

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
    outDir: "dist",
    emptyOutDir: true,
    assetsDir: "assets",
    // 确保生成正确的资源URL
    assetsInlineLimit: 4096,
    // 生成sourcemap以便调试
    sourcemap: true,
    // 明确指定入口文件
    rollupOptions: {
      input: resolve(__dirname, "index.html"),
    },
  },
  // 确保正确解析路径别名
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
});
