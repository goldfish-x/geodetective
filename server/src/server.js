import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import fastifyStatic from "@fastify/static";
import { buildApp } from "./app.js";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const DIST = HERE + "../../web/dist";

const app = buildApp({ logger: true, dbFile: process.env.GD_DB || (HERE + "../../server-data/db.json") })

// 档 A 单端口部署：BFF 同时托管前端产物（SPA 回落到 index.html）
if (existsSync(DIST + "/index.html")) {
  await app.register(fastifyStatic, { root: DIST, prefix: "/", wildcard: false })
  app.setNotFoundHandler((req, rep) => {
    if (req.raw.method === "GET" && !req.raw.url.startsWith("/v1/"))
      return rep.type("text/html").sendFile("index.html")
    return rep.code(404).send({ error: "not_found" })
  })
}

const port = Number(process.env.PORT || 8787)
const host = process.env.HOST || "0.0.0.0"
app.listen({ port, host }).then(() => {
  app.log.info(`geo-detective-api listening on http://${host}:${port}`)
}).catch(err => {
  app.log.error(err)
  process.exit(1)
})
