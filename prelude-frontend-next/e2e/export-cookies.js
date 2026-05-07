/**
 * Helper: Export cookies from a running Playwright MCP browser session.
 * Called via: node e2e/export-cookies.js <cookie-json-string>
 *
 * The MCP skill reads cookies from the browser via browser_evaluate,
 * then passes them to this script to save as cookies.json.
 */

const fs = require('fs')
const path = require('path')

const cookiesJson = process.argv[2]
if (!cookiesJson) {
  console.error('Usage: node export-cookies.js <cookies-json-string>')
  process.exit(1)
}

try {
  const cookies = JSON.parse(cookiesJson)
  const outPath = path.join(__dirname, 'cookies.json')
  fs.writeFileSync(outPath, JSON.stringify(cookies, null, 2))
  console.log(`Saved ${cookies.length} cookies to ${outPath}`)
} catch (err) {
  console.error('Failed to parse cookies:', err.message)
  process.exit(1)
}
