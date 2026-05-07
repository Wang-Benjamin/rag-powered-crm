/**
 * Localization E2E Test Suite
 *
 * Verifies both en and zh-CN flows work end-to-end.
 * Extends the existing Playwright harness in run-test.js.
 *
 * Usage: node e2e/run-test.js localization [environment]
 *
 * Prerequisites:
 * - Frontend running (npm run dev)
 * - Backends running with matching JWT_SECRET
 */

const {
  setTestLocale,
  assertPageLocale,
  assertLangEn,
  assertContainsChinese,
  assertEnglishOnly,
} = require('./helpers/locale')

// --- English (en) tests ---

async function testEnglishCRM(page, log, screenshot, navigateSidebar, waitForLoad) {
  await setTestLocale(page, 'en')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForLoad(page)

  await navigateSidebar(page, 'Customer Relations')
  const table = page.locator('table').first()
  await table.waitFor({ state: 'visible', timeout: 30000 })

  // Verify English headers
  const headers = await page.locator('table th').allTextContents()
  const hasEnglish = headers.some((h) => /Company|Status|Contact/i.test(h))
  if (hasEnglish) {
    log('EN: CRM headers', 'PASS', headers.filter((h) => h.trim()).join(', '))
  } else {
    log('EN: CRM headers', 'FAIL', 'Expected English headers')
  }

  await screenshot(page, 'en-crm-table')
}

async function testEnglishDeals(page, log, screenshot, navigateSidebar, waitForLoad) {
  await navigateSidebar(page, 'Deals')
  await waitForLoad(page)

  const table = page.locator('table').first()
  await table.waitFor({ state: 'visible', timeout: 15000 }).catch(() => {})

  const headers = await page.locator('table th').allTextContents()
  const hasEnglish = headers.some((h) => /Deal|Stage|Value|Client/i.test(h))
  if (hasEnglish) {
    log('EN: Deals headers', 'PASS', headers.filter((h) => h.trim()).join(', '))
  } else {
    log('EN: Deals headers', 'FAIL', 'Expected English deal headers')
  }

  await screenshot(page, 'en-deals-table')
}

async function testEnglishNav(page, log, screenshot) {
  // Check sidebar has English labels
  const sidebar = page.locator('nav').first()
  const text = await sidebar.textContent()

  const hasEnglish = /Customer Relations|Lead Generation|Deals|Settings/.test(text)
  if (hasEnglish) {
    log('EN: Navigation', 'PASS', 'English sidebar labels')
  } else {
    log('EN: Navigation', 'FAIL', 'Expected English sidebar labels')
  }

  await screenshot(page, 'en-navigation')
}

// --- Simplified Chinese (zh-CN) tests ---

async function testChineseLocale(page, log, screenshot, navigateSidebar, waitForLoad) {
  await setTestLocale(page, 'zh-CN')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForLoad(page)

  // Verify html lang attribute
  try {
    await assertPageLocale(page, 'zh-CN')
    log('ZH: html lang', 'PASS', 'lang="zh-CN"')
  } catch (e) {
    log('ZH: html lang', 'FAIL', e.message)
  }
}

async function testChineseCRM(page, log, screenshot, navigateSidebar, waitForLoad) {
  // Navigate using Chinese label
  const crmButton = page.getByRole('button', { name: /客户关系|Customer Relations/ })
  await crmButton.click()
  await waitForLoad(page)

  const table = page.locator('table').first()
  await table.waitFor({ state: 'visible', timeout: 30000 })

  // Table headers should be in Chinese
  const headers = await page.locator('table th').allTextContents()
  const hasChinese = headers.some((h) => /[\u4e00-\u9fff]/.test(h))
  if (hasChinese) {
    log('ZH: CRM headers', 'PASS', headers.filter((h) => h.trim()).join(', '))
  } else {
    log('ZH: CRM headers', 'FAIL', 'Expected Chinese headers')
  }

  // Table data cells should have lang="en" (English business data)
  const firstDataCell = page.locator('table tbody td').first()
  const cellLang = await firstDataCell.getAttribute('lang').catch(() => null)
  if (cellLang === 'en') {
    log('ZH: Data cells lang="en"', 'PASS', 'English data annotated')
  } else {
    log('ZH: Data cells lang="en"', 'FAIL', `Got lang="${cellLang}"`)
  }

  await screenshot(page, 'zh-crm-table')
}

async function testChineseNav(page, log, screenshot) {
  const sidebar = page.locator('nav').first()
  const text = await sidebar.textContent()

  const hasChinese = /[\u4e00-\u9fff]/.test(text)
  if (hasChinese) {
    log('ZH: Navigation', 'PASS', 'Chinese sidebar labels')
  } else {
    log('ZH: Navigation', 'FAIL', 'Expected Chinese sidebar labels')
  }

  await screenshot(page, 'zh-navigation')
}

// --- Mixed-language UX tests ---

async function testMixedLanguageUX(page, log, screenshot) {
  // Verify table has Chinese headers + English data
  const headers = await page.locator('table th').allTextContents()
  const hasChinese = headers.some((h) => /[\u4e00-\u9fff]/.test(h))

  const firstRow = page.locator('table tbody tr').first()
  const rowText = await firstRow.textContent().catch(() => '')

  if (hasChinese && /[A-Za-z]/.test(rowText)) {
    log('Mixed: Chinese headers + English data', 'PASS', 'Correct mixed-language UX')
  } else {
    log('Mixed: Chinese headers + English data', 'FAIL', 'Unexpected language mix')
  }

  await screenshot(page, 'zh-mixed-language')
}

// --- Locale switching tests ---

async function testLocaleSwitching(page, log, screenshot, waitForLoad) {
  // Switch from zh-CN back to en
  await setTestLocale(page, 'en')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await waitForLoad(page)

  try {
    await assertPageLocale(page, 'en')
    log('Switch: zh-CN → en', 'PASS', 'Cookie switch works')
  } catch (e) {
    log('Switch: zh-CN → en', 'FAIL', e.message)
  }

  // Verify English content after switch
  const sidebar = page.locator('nav').first()
  const text = await sidebar.textContent()
  if (/Customer Relations/.test(text)) {
    log('Switch: English restored', 'PASS', 'English labels after switch')
  } else {
    log('Switch: English restored', 'FAIL', 'Expected English after locale switch')
  }

  await screenshot(page, 'switch-back-to-en')
}

// --- Main test runner ---

async function testLocalization(page, log, screenshot, navigateSidebar, waitForLoad) {
  // English tests
  await testEnglishCRM(page, log, screenshot, navigateSidebar, waitForLoad)
  await testEnglishDeals(page, log, screenshot, navigateSidebar, waitForLoad)
  await testEnglishNav(page, log, screenshot)

  // Chinese tests
  await testChineseLocale(page, log, screenshot, navigateSidebar, waitForLoad)
  await testChineseCRM(page, log, screenshot, navigateSidebar, waitForLoad)
  await testChineseNav(page, log, screenshot)

  // Mixed-language UX
  await testMixedLanguageUX(page, log, screenshot)

  // Locale switching
  await testLocaleSwitching(page, log, screenshot, waitForLoad)
}

module.exports = { testLocalization }
