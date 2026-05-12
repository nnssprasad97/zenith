import { VERSION } from './version'
import { Server } from 'ws'
import { chromium, Browser, Page } from 'playwright'

console.log(`[Node.js Bridge] Starting Zenith Node.js Bridge v${VERSION}`)

class NodeBridge {
  private wss: Server
  private browser: Browser | null = null
  private page: Page | null = null

  constructor(port = 1339) {
    this.wss = new Server({ port })
    this.setupWebSocket()
    this.initBrowser()
  }

  private async initBrowser() {
    try {
      this.browser = await chromium.launch({ headless: true })
      console.log('[Node.js Bridge] Playwright browser automation ready.')
    } catch (e) {
      console.error('[Node.js Bridge] Failed to init Playwright:', e)
    }
  }

  private setupWebSocket() {
    this.wss.on('connection', (ws) => {
      console.log('[Node.js Bridge] Client connected.')
      
      ws.on('message', async (message) => {
        try {
          const payload = JSON.parse(message.toString())
          const result = await this.handleCommand(payload)
          ws.send(JSON.stringify({ type: 'response', ...result }))
        } catch (err) {
          ws.send(JSON.stringify({ type: 'error', message: String(err) }))
        }
      })
    })
  }

  private async handleCommand(payload: any) {
    if (payload.action === 'navigate' && this.browser) {
      if (!this.page) this.page = await this.browser.newPage()
      await this.page.goto(payload.url)
      const title = await this.page.title()
      return { success: true, title }
    }
    return { success: false, message: 'Unknown command or browser not ready.' }
  }
}

// Start the bridge
const bridge = new NodeBridge()

