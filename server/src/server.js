import { buildApp } from './app.js'

const app = buildApp({ logger: true })
const port = Number(process.env.PORT || 8787)
const host = process.env.HOST || '127.0.0.1'
app.listen({ port, host }).then(() => {
  app.log.info(`geo-detective-api listening on http://${host}:${port}`)
}).catch(err => {
  app.log.error(err)
  process.exit(1)
})
