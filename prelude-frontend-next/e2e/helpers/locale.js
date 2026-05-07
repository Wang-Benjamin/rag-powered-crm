/**
 * Locale helpers for E2E tests.
 *
 * Usage:
 *   const { setTestLocale, assertPageLocale } = require('./helpers/locale');
 *   await setTestLocale(page, 'zh-CN');
 *   await assertPageLocale(page, 'zh-CN');
 */

/**
 * Set the NEXT_LOCALE cookie for E2E tests.
 * Call before navigating to pages that should render in a specific locale.
 */
async function setTestLocale(page, locale) {
  await page.context().addCookies([
    {
      name: 'NEXT_LOCALE',
      value: locale,
      domain: 'localhost',
      path: '/',
    },
  ])
}

/**
 * Assert that the page renders in the expected locale.
 * Checks the html lang attribute.
 */
async function assertPageLocale(page, expectedLocale) {
  const lang = await page.getAttribute('html', 'lang')
  if (lang !== expectedLocale) {
    throw new Error(`Expected html lang="${expectedLocale}", got "${lang}"`)
  }
}

/**
 * Assert that an element has lang="en" (English data region).
 */
async function assertLangEn(locator) {
  const lang = await locator.getAttribute('lang')
  if (lang !== 'en') {
    throw new Error(`Expected lang="en", got "${lang}"`)
  }
}

/**
 * Assert text content contains Chinese characters.
 */
async function assertContainsChinese(locator) {
  const text = await locator.textContent()
  if (!/[\u4e00-\u9fff]/.test(text)) {
    throw new Error(`Expected Chinese characters in: "${text.substring(0, 100)}"`)
  }
}

/**
 * Assert text content is English-only (no Chinese characters).
 */
async function assertEnglishOnly(locator) {
  const text = await locator.textContent()
  if (/[\u4e00-\u9fff]/.test(text)) {
    throw new Error(`Expected English only but found Chinese in: "${text.substring(0, 100)}"`)
  }
}

module.exports = {
  setTestLocale,
  assertPageLocale,
  assertLangEn,
  assertContainsChinese,
  assertEnglishOnly,
}
