#!/usr/bin/env node

/**
 * CI Translation Key Checker
 * Compares key sets between messages/en/*.json and messages/zh-CN/*.json.
 * Flags any keys present in en but missing in zh-CN.
 *
 * Usage: node scripts/check-translations.js
 * Exit code 1 if missing keys found, 0 if all keys match.
 */

const fs = require('fs')
const path = require('path')

const MESSAGES_DIR = path.join(__dirname, '..', 'messages')
const LOCALES = ['en', 'zh-CN']
const BASE_LOCALE = 'en'

function getJsonFiles(locale) {
  const dir = path.join(MESSAGES_DIR, locale)
  if (!fs.existsSync(dir)) return []
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.json'))
    .sort()
}

function flattenKeys(obj, prefix = '') {
  const keys = []
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      keys.push(...flattenKeys(value, fullKey))
    } else {
      keys.push(fullKey)
    }
  }
  return keys
}

function loadAndFlatten(locale, file) {
  const filePath = path.join(MESSAGES_DIR, locale, file)
  if (!fs.existsSync(filePath)) return []
  const content = JSON.parse(fs.readFileSync(filePath, 'utf-8'))
  return flattenKeys(content)
}

let hasErrors = false

// Check that all locales have the same files as base
const baseFiles = getJsonFiles(BASE_LOCALE)

for (const locale of LOCALES.filter((l) => l !== BASE_LOCALE)) {
  const localeFiles = getJsonFiles(locale)

  // Check for missing files
  for (const file of baseFiles) {
    if (!localeFiles.includes(file)) {
      console.error(`MISSING FILE: ${locale}/${file} (exists in ${BASE_LOCALE})`)
      hasErrors = true
      continue
    }

    // Compare keys
    const baseKeys = new Set(loadAndFlatten(BASE_LOCALE, file))
    const localeKeys = new Set(loadAndFlatten(locale, file))

    const missingInLocale = [...baseKeys].filter((k) => !localeKeys.has(k))
    const extraInLocale = [...localeKeys].filter((k) => !baseKeys.has(k))

    if (missingInLocale.length > 0) {
      console.error(`\nMISSING KEYS in ${locale}/${file}:`)
      missingInLocale.forEach((k) => console.error(`  - ${k}`))
      hasErrors = true
    }

    if (extraInLocale.length > 0) {
      console.warn(`\nEXTRA KEYS in ${locale}/${file} (not in ${BASE_LOCALE}):`)
      extraInLocale.forEach((k) => console.warn(`  + ${k}`))
    }
  }

  // Check for extra files in locale
  for (const file of localeFiles) {
    if (!baseFiles.includes(file)) {
      console.warn(`EXTRA FILE: ${locale}/${file} (not in ${BASE_LOCALE})`)
    }
  }
}

if (hasErrors) {
  console.error('\nTranslation check FAILED — missing keys detected.')
  process.exit(1)
} else {
  // Count total keys
  let totalKeys = 0
  for (const file of baseFiles) {
    totalKeys += loadAndFlatten(BASE_LOCALE, file).length
  }
  console.log(
    `Translation check PASSED — ${totalKeys} keys across ${baseFiles.length} files, all locales in sync.`
  )
  process.exit(0)
}
