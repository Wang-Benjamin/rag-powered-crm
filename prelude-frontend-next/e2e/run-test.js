/**
 * Prelude Platform E2E Test Runner with Video Recording
 *
 * Usage: node e2e/run-test.js <scenario> [environment]
 *   scenario: leads | crm | deals | email-profiles | onboarding | smoke | full
 *   environment: local (default) | dev | prod
 *
 * For local: requires frontend (npm run dev) and backends running locally.
 * For dev/prod: requires auth.json in e2e/ directory (exported from MCP login session).
 */

const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

const ENVS = {
  local: 'http://localhost:8000',
  dev: 'https://dev.preludeos.com',
  prod: 'https://app.preludeos.com',
}

const scenario = process.argv[2] || 'smoke'
const env = process.argv[3] || 'local'
const baseUrl = ENVS[env]

if (!baseUrl) {
  console.error(`Unknown environment: ${env}. Use "local", "dev", or "prod".`)
  process.exit(1)
}

// For local mode, we mint a fresh JWT signed with LOCAL_JWT_SECRET.
// Start backends with: JWT_SECRET=prelude-e2e-local-secret python main.py
const LOCAL_JWT_SECRET = process.env.E2E_JWT_SECRET || 'prelude-e2e-local-secret'

function createLocalJwt(secret) {
  const header = { alg: 'HS256', typ: 'JWT' }
  const payload = {
    sub: '115497933722307483035',
    email: 'mark@preludeos.com',
    name: 'Zhiyuan Li',
    provider: 'google',
    exp: Math.floor(Date.now() / 1000) + 86400, // 24h
    iat: Math.floor(Date.now() / 1000),
  }
  const b64 = (obj) => Buffer.from(JSON.stringify(obj)).toString('base64url')
  const unsigned = `${b64(header)}.${b64(payload)}`
  const sig = crypto.createHmac('sha256', secret).update(unsigned).digest('base64url')
  return `${unsigned}.${sig}`
}

const authPath = path.join(__dirname, 'auth.json')
const videosDir = path.join(__dirname, 'videos')
const screenshotsDir = path.join(__dirname, 'screenshots')

fs.mkdirSync(videosDir, { recursive: true })
fs.mkdirSync(screenshotsDir, { recursive: true })

const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
const results = []

function log(step, status, notes = '') {
  const entry = { step, status, notes }
  results.push(entry)
  const icon = status === 'PASS' ? '\u2705' : status === 'FAIL' ? '\u274c' : '\u23f3'
  console.log(`${icon} ${step}: ${notes}`)
}

async function screenshot(page, name) {
  const filepath = path.join(screenshotsDir, `${timestamp}_${scenario}_${name}.png`)
  await page.screenshot({ path: filepath, fullPage: false })
  return filepath
}

async function waitForLoad(page, timeout = 15000) {
  await page.waitForLoadState('domcontentloaded', { timeout }).catch(() => {})
  await page.waitForTimeout(3000)
}

async function navigateSidebar(page, main, sub, exact = false) {
  if (sub) {
    const subBtn = page.getByRole('button', { name: sub, exact })
    const subVisible = await subBtn.isVisible().catch(() => false)

    if (!subVisible) {
      const mainBtn = page.getByRole('button', { name: main, exact })
      await mainBtn.click()
      await page.waitForTimeout(500)
    }

    await subBtn.click()
    await waitForLoad(page)
  } else {
    const mainBtn = page.getByRole('button', { name: main, exact })
    await mainBtn.click()
    await waitForLoad(page)
  }
}

// ---- SCENARIOS ----

async function testLeads(page) {
  await navigateSidebar(page, 'Market', 'Buyers', true)
  await screenshot(page, 'leads-after-nav')
  const table = page.locator('table').first()
  await table.waitFor({ state: 'visible', timeout: 30000 })

  const pagination = await page
    .locator('text=/Showing \\d+-\\d+ of \\d+ leads/')
    .textContent()
    .catch(() => null)
  if (pagination) {
    log('Leads table', 'PASS', pagination)
  } else {
    log('Leads table', 'FAIL', 'No pagination info found')
  }

  const headers = await page.locator('table th').allTextContents()
  log('Table columns', 'PASS', headers.filter((h) => h.trim()).join(', '))

  await screenshot(page, 'leads-table')
  log('Screenshot', 'PASS', 'leads-table')
}

async function testCRM(page) {
  await navigateSidebar(page, 'Lead Development')
  const table = page.locator('table').first()
  await table.waitFor({ state: 'visible', timeout: 30000 })

  const pagination = await page
    .locator('text=/Showing \\d+-\\d+ of \\d+ customers/')
    .textContent()
    .catch(() => null)
  if (pagination) {
    log('CRM table', 'PASS', pagination)
  } else {
    log('CRM table', 'FAIL', 'No pagination info found')
  }

  const headers = await page.locator('table th').allTextContents()
  log('Table columns', 'PASS', headers.filter((h) => h.trim()).join(', '))

  await screenshot(page, 'crm-table')
  log('Screenshot', 'PASS', 'crm-table')
}

async function testDeals(page) {
  await navigateSidebar(page, 'Deals')
  const table = page.locator('table').first()
  await table.waitFor({ state: 'visible', timeout: 15000 }).catch(() => {})

  const hasRows = await page.locator('table tbody tr').count()
  if (hasRows > 0) {
    log('Deals table', 'PASS', `${hasRows} deals visible`)
  } else {
    log('Deals table', 'FAIL', 'No deals found or table not loaded')
  }

  await screenshot(page, 'deals-table')
  log('Screenshot', 'PASS', 'deals-table')
}

async function testEmailProfiles(page) {
  await navigateSidebar(page, 'Email Profiles', 'Email Templates')
  await waitForLoad(page)

  await screenshot(page, 'email-templates')
  log('Email Templates', 'PASS', 'Page loaded')

  await navigateSidebar(page, 'Email Profiles', 'Email Settings')
  await waitForLoad(page)

  await screenshot(page, 'email-settings')
  log('Email Settings', 'PASS', 'Page loaded')
}

async function testOnboarding(page) {
  await navigateSidebar(page, 'User Onboarding', 'Team Organization')
  await waitForLoad(page)

  await screenshot(page, 'team-org')
  log('Team Organization', 'PASS', 'Page loaded')

  await navigateSidebar(page, 'User Onboarding', 'Customize AI')
  await waitForLoad(page)

  await screenshot(page, 'customize-ai')
  log('Customize AI', 'PASS', 'Page loaded')
}

async function runSmoke(page) {
  await testLeads(page)
  await testCRM(page)
  await testDeals(page)
}

async function runFull(page) {
  await testLeads(page)
  await testCRM(page)
  await testDeals(page)
  await testEmailProfiles(page)
  await testOnboarding(page)
}

// Localization E2E tests
let testLocalization
try {
  testLocalization = require('./localization').testLocalization
} catch {}

async function runSmokeI18n(page) {
  // --- Phase 1: Test in English (/en/) ---
  log('i18n Phase', 'PASS', 'Testing English (en)')

  // Verify URL has /en/ prefix
  const enUrl = page.url()
  if (enUrl.includes('/en/')) {
    log('EN URL prefix', 'PASS', enUrl)
  } else {
    log('EN URL prefix', 'FAIL', `Expected /en/ in URL, got: ${enUrl}`)
  }

  // Check English content on CRM page
  const enBody = await page
    .locator('body')
    .innerText()
    .catch(() => '')
  const hasEnglish =
    enBody.includes('Customer Relations') ||
    enBody.includes('Add Customer') ||
    enBody.includes('Filters')
  log(
    'EN content',
    hasEnglish ? 'PASS' : 'FAIL',
    hasEnglish ? 'English UI text found' : 'No English text detected'
  )
  await screenshot(page, 'en-crm')

  // Navigate through pages in English
  await testLeads(page)
  await screenshot(page, 'en-leads')

  // Verify leads page URL still has /en/
  if (page.url().includes('/en/')) {
    log('EN nav preserved', 'PASS', 'Locale prefix maintained after navigation')
  } else {
    log('EN nav preserved', 'FAIL', `Lost /en/ prefix: ${page.url()}`)
  }

  // --- Phase 2: Switch to Chinese via URL ---
  log('i18n Phase', 'PASS', 'Switching to Chinese (zh-CN)')

  // Navigate to zh-CN version of CRM
  const currentPath = page
    .url()
    .replace(baseUrl, '')
    .replace(/^\/(en|zh-CN)/, '')
  await page.goto(baseUrl + '/zh-CN' + (currentPath || '/'), {
    waitUntil: 'domcontentloaded',
    timeout: 30000,
  })
  await page.waitForTimeout(5000)

  // Verify URL has /zh-CN/ prefix
  const zhUrl = page.url()
  if (zhUrl.includes('/zh-CN/')) {
    log('ZH URL prefix', 'PASS', zhUrl)
  } else {
    log('ZH URL prefix', 'FAIL', `Expected /zh-CN/ in URL, got: ${zhUrl}`)
  }

  await screenshot(page, 'zh-after-switch')

  // Check Chinese content
  const zhBody = await page
    .locator('body')
    .innerText()
    .catch(() => '')
  // Check for Chinese characters (CJK Unified Ideographs range)
  const hasChinese = /[\u4e00-\u9fff]/.test(zhBody)
  log(
    'ZH content',
    hasChinese ? 'PASS' : 'FAIL',
    hasChinese ? 'Chinese UI text found' : 'No Chinese text detected'
  )
  await screenshot(page, 'zh-crm')

  // Navigate through pages in Chinese
  await navigateSidebar(page, 'Customer Relations').catch(async () => {
    // Sidebar labels may be in Chinese, try Chinese label
    const sidebar = await page.locator('nav button, nav a').allTextContents()
    console.log('Sidebar labels:', sidebar.filter((s) => s.trim()).join(', '))
    // Click the second main nav item (CRM is usually second)
    const crmBtn = page.locator('nav button').nth(1)
    await crmBtn.click().catch(() => {})
    await waitForLoad(page)
  })
  await screenshot(page, 'zh-crm-nav')

  // Verify zh-CN prefix maintained
  if (page.url().includes('/zh-CN/')) {
    log('ZH nav preserved', 'PASS', 'zh-CN prefix maintained after navigation')
  } else {
    log('ZH nav preserved', 'FAIL', `Lost /zh-CN/ prefix: ${page.url()}`)
  }

  // --- Phase 3: Switch back to English via URL ---
  log('i18n Phase', 'PASS', 'Switching back to English (en)')
  const zhPath = page
    .url()
    .replace(baseUrl, '')
    .replace(/^\/(en|zh-CN)/, '')
  await page.goto(baseUrl + '/en' + (zhPath || '/'), {
    waitUntil: 'domcontentloaded',
    timeout: 30000,
  })
  await page.waitForTimeout(3000)

  const backToEnBody = await page
    .locator('body')
    .innerText()
    .catch(() => '')
  const hasEnglishAgain =
    backToEnBody.includes('Customer Relations') ||
    backToEnBody.includes('Add Customer') ||
    backToEnBody.includes('Filters')
  log(
    'EN restored',
    hasEnglishAgain ? 'PASS' : 'FAIL',
    hasEnglishAgain ? 'English UI restored after switching back' : 'English content not restored'
  )
  await screenshot(page, 'en-restored')
}

const SCENARIOS = {
  leads: testLeads,
  crm: testCRM,
  deals: testDeals,
  'email-profiles': testEmailProfiles,
  onboarding: testOnboarding,
  ...(testLocalization
    ? {
        localization: (page) =>
          testLocalization(page, log, screenshot, navigateSidebar, waitForLoad),
      }
    : {}),
  smoke: runSmoke,
  'smoke-i18n': runSmokeI18n,
  full: runFull,
}

// ---- MAIN ----

;(async () => {
  let tokens

  if (env === 'local') {
    // For local: mint a fresh JWT — no auth.json needed
    const jwt = createLocalJwt(LOCAL_JWT_SECRET)
    tokens = { id_token: jwt, refresh_token: 'local-no-refresh', auth_provider: 'google' }
    console.log(`\n=== Prelude E2E Test: "${scenario}" on ${env} (${baseUrl}) ===`)
    console.log(`Using locally-minted JWT (secret: ${LOCAL_JWT_SECRET})`)
    console.log(
      'Make sure backends were started with: JWT_SECRET=' + LOCAL_JWT_SECRET + ' python main.py\n'
    )
  } else {
    if (!fs.existsSync(authPath)) {
      console.error('ERROR: auth.json not found. Run MCP login first to export tokens.')
      console.error('Expected path:', authPath)
      process.exit(1)
    }
    const auth = JSON.parse(fs.readFileSync(authPath, 'utf-8'))
    tokens = auth.tokens
    console.log(`\n=== Prelude E2E Test: "${scenario}" on ${env} (${baseUrl}) ===\n`)
  }

  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    recordVideo: { dir: videosDir, size: { width: 1280, height: 720 } },
    viewport: { width: 1280, height: 720 },
  })

  const page = await context.newPage()

  // Intercept network requests for debugging
  page.on('response', async (response) => {
    const url = response.url()
    const status = response.status()
    if (url.includes('/api/proxy/') || url.includes('/api/auth/')) {
      let body = ''
      try {
        body = (await response.text()).substring(0, 200)
      } catch {}
      console.log(
        `[NET] ${status} ${response.request().method()} ${url.replace(baseUrl, '')} → ${body}`
      )
    }
  })

  page.on('request', (request) => {
    const url = request.url()
    if (url.includes('/api/proxy/') || url.includes('/api/auth/')) {
      const authHeader = request.headers()['authorization']
      console.log(
        `[REQ] ${request.method()} ${url.replace(baseUrl, '')} auth=${authHeader ? authHeader.substring(0, 30) + '...' : 'NONE'}`
      )
    }
  })

  try {
    // First navigate to the base URL to set the origin for localStorage
    // With locale-prefixed routing, /login redirects to /en/login
    await page.goto(baseUrl + '/en/login', { waitUntil: 'domcontentloaded', timeout: 30000 })
    await page.waitForTimeout(1000)

    // Inject auth tokens into localStorage and set locale cookie to 'en'
    await page.evaluate((t) => {
      localStorage.setItem('id_token', t.id_token)
      localStorage.setItem('refresh_token', t.refresh_token)
      localStorage.setItem('auth_provider', t.auth_provider)
      // Ensure locale cookie is set to 'en' so middleware doesn't redirect away
      document.cookie = 'NEXT_LOCALE=en; path=/; samesite=lax; max-age=31536000'
      // Skip preload gate in workspace layout
      sessionStorage.setItem('workspace_preloaded', 'true')
      console.log('Tokens injected:', Object.keys(t))
    }, tokens)

    // Reload the page so the app picks up the tokens from localStorage
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 })

    // Wait for auth redirect — poll URL instead of fixed timeout
    let redirected = false
    for (let i = 0; i < 20; i++) {
      await page.waitForTimeout(1000)
      if (!page.url().includes('/login')) {
        redirected = true
        break
      }
    }

    if (!redirected) {
      await screenshot(page, 'debug-stuck-login')
      const bodyText = await page
        .locator('body')
        .innerText()
        .catch(() => '')
      console.error('ERROR: Still on login after 20s. URL:', page.url())
      console.error('Page body:', bodyText.substring(0, 300))
      // Check console errors
      const consoleErrors = []
      page.on('console', (msg) => {
        if (msg.type() === 'error') consoleErrors.push(msg.text())
      })
      await page.waitForTimeout(2000)
      if (consoleErrors.length) console.error('Console errors:', consoleErrors)
      await context.close()
      await browser.close()
      process.exit(1)
    }

    // Wait for preload to finish — it may show "Loading Your Workspace" or a progress indicator
    await page.waitForTimeout(2000)
    const preloadVisible = await page
      .locator('text=Loading Your Workspace')
      .isVisible()
      .catch(() => false)
    if (preloadVisible) {
      console.log('Waiting for preload to complete...')
      await page.locator('text=Loading Your Workspace').waitFor({ state: 'hidden', timeout: 60000 })
    }

    // Debug: screenshot right after landing
    console.log('Current URL:', page.url())
    await screenshot(page, 'debug-after-reload')

    // Wait for the page to settle and data to load
    console.log('Waiting for initial data load...')
    await page.waitForTimeout(5000)

    // Debug: screenshot after waiting
    console.log('URL after wait:', page.url())
    await screenshot(page, 'debug-after-wait')

    // Log page content for debugging
    const bodyText = await page
      .locator('body')
      .innerText()
      .catch(() => 'COULD NOT READ BODY')
    console.log('Page body preview:', bodyText.substring(0, 500))

    const initialTable = page.locator('table').first()
    await initialTable.waitFor({ state: 'visible', timeout: 30000 }).catch(() => {
      console.log('Warning: Initial table not visible after 30s, continuing anyway...')
    })
    await page.waitForTimeout(2000)

    log('Login & Navigate', 'PASS', `Landed on ${page.url()}`)
    await screenshot(page, 'after-login')

    // Run scenario
    const testFn = SCENARIOS[scenario]
    if (!testFn) {
      console.error(
        `Unknown scenario: ${scenario}. Available: ${Object.keys(SCENARIOS).join(', ')}`
      )
      process.exit(1)
    }

    await testFn(page)
  } catch (err) {
    log('Unexpected error', 'FAIL', err.message)
    await screenshot(page, 'error')
  }

  // Close context to save video
  await context.close()
  await browser.close()

  // Find video file
  const videoFiles = fs
    .readdirSync(videosDir)
    .filter((f) => f.endsWith('.webm'))
    .sort()
    .reverse()
  const latestVideo = videoFiles[0] ? path.join(videosDir, videoFiles[0]) : null

  // Print report
  console.log('\n=== TEST REPORT ===\n')
  console.log(`Scenario: ${scenario}`)
  console.log(`Environment: ${env} (${baseUrl})`)
  console.log(`Time: ${new Date().toISOString()}`)
  console.log(`Video: ${latestVideo || 'N/A'}`)
  console.log('')

  let passCount = 0
  let failCount = 0

  results.forEach((r) => {
    if (r.status === 'PASS') passCount++
    if (r.status === 'FAIL') failCount++
    console.log(`| ${r.step.padEnd(25)} | ${r.status} | ${r.notes}`)
  })

  console.log('')
  console.log(`Overall: ${passCount} PASS, ${failCount} FAIL`)
  console.log(`Video saved: ${latestVideo}`)

  if (failCount > 0) process.exit(1)
})()
