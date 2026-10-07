// 无需安装依赖的本地静态文件服务器。WebSocket 游戏服务器仍然由 C++ 提供。
import { createServer } from "node:http";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { dirname, extname, relative, resolve, isAbsolute, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.PORT || 8000);
const mime = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript",
  ".svg": "image/svg+xml", ".json": "application/json", ".md": "text/plain" };
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("PORT 必须是 1 到 65535 之间的整数。");

const server = createServer(async (request, response) => {
  if (!["GET", "HEAD"].includes(request.method)) {
    response.writeHead(405, { Allow: "GET, HEAD" }).end();
    return;
  }
  try {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    const file = resolve(root, `.${pathname === "/" ? "/index.html" : pathname}`);
    const local = relative(root, file);
    if (local === ".." || local.startsWith(`..${sep}`) || isAbsolute(local)) {
      response.writeHead(403).end("Forbidden");
      return;
    }
    const info = await stat(file);
    if (!info.isFile()) { response.writeHead(404).end("Not found"); return; }
    response.writeHead(200, { "Content-Type": `${mime[extname(file)] || "application/octet-stream"}; charset=utf-8`,
      "Content-Length": info.size, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
    if (request.method === "HEAD") response.end();
    else createReadStream(file).on("error", () => response.destroy()).pipe(response);
  } catch (error) {
    response.writeHead(error.code === "ENOENT" ? 404 : 400).end("Cannot read this file");
  }
});
server.on("error", (error) => { console.error(`网页服务器启动失败：${error.message}`); process.exitCode = 1; });
server.listen(port, "0.0.0.0", () => console.log(`网页已启动：http://localhost:${port}\n游戏服务器地址：ws://localhost:18080/ws\n按 Ctrl+C 停止网页服务器。`));
