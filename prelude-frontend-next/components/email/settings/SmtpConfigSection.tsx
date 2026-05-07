'use client'

import React, { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { Mail, CheckCircle, XCircle, Trash2, Server } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { smtpApi, type SmtpConfig, type SmtpPreset } from '@/lib/api/emailprofiles'

const PRESET_KEYS = ['qq', '163', 'outlook', 'gmail', 'custom'] as const

export function SmtpConfigSection() {
  const t = useTranslations('settings')
  const [config, setConfig] = useState<SmtpConfig>({
    providerName: 'qq',
    smtpHost: '',
    smtpPort: 587,
    smtpUser: '',
    smtpPassword: '',
    imapHost: '',
    imapPort: 993,
    fromName: '',
  })
  const [presets, setPresets] = useState<Record<string, SmtpPreset>>({})
  const [existingConfig, setExistingConfig] = useState<SmtpConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ smtpOk: boolean; smtpError?: string; imapOk: boolean; imapError?: string } | null>(null)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle')

  useEffect(() => {
    async function load() {
      try {
        const [presetsData, configData] = await Promise.all([
          smtpApi.getPresets(),
          smtpApi.getConfig(),
        ])
        setPresets(presetsData)
        if (configData) {
          setExistingConfig(configData)
          setConfig({ ...configData, smtpPassword: '' })
        }
      } catch {
        // Non-blocking
      }
    }
    load()
  }, [])

  const handlePresetChange = (key: string) => {
    const preset = presets[key]
    if (preset) {
      setConfig((prev) => ({
        ...prev,
        providerName: key,
        smtpHost: preset.smtpHost,
        smtpPort: preset.smtpPort,
        imapHost: preset.imapHost,
        imapPort: preset.imapPort,
      }))
    } else {
      setConfig((prev) => ({ ...prev, providerName: key }))
    }
    setTestResult(null)
    setSaveStatus('idle')
  }

  const handleSave = async () => {
    if (!config.smtpHost || !config.smtpUser || !config.smtpPassword) return
    setSaving(true)
    setSaveStatus('idle')
    try {
      const result = await smtpApi.saveConfig(config)
      setExistingConfig(result)
      setSaveStatus('success')
    } catch {
      setSaveStatus('error')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await smtpApi.testConfig()
      setTestResult(result)
      if (result.smtpOk && result.imapOk) {
        setExistingConfig((prev) => prev ? { ...prev, verified: true } : prev)
      }
    } catch {
      setTestResult({ smtpOk: false, smtpError: 'Request failed', imapOk: false, imapError: 'Request failed' })
    } finally {
      setTesting(false)
    }
  }

  const handleDelete = async () => {
    try {
      await smtpApi.deleteConfig()
      setExistingConfig(null)
      setConfig({ providerName: 'qq', smtpHost: '', smtpPort: 587, smtpUser: '', smtpPassword: '', imapHost: '', imapPort: 993, fromName: '' })
      setTestResult(null)
      setSaveStatus('idle')
    } catch {
      // ignore
    }
  }

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-700 dark:bg-zinc-900">
      <div className="mb-4 flex items-center gap-2">
        <Server className="h-4 w-4 text-zinc-500" />
        <h3 className="title-panel">
          {t('smtp.title')}
        </h3>
        {existingConfig?.verified && (
          <span className="flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
            <CheckCircle className="h-3 w-3" /> {t('smtp.verified')}
          </span>
        )}
      </div>

      <p className="mb-4 text-xs text-zinc-500 dark:text-zinc-400">
        {t('smtp.description')}
      </p>

      {/* Provider preset selector */}
      <div className="mb-4">
        <Label className="mb-1.5 text-xs">{t('smtp.provider')}</Label>
        <div className="flex flex-wrap gap-2">
          {PRESET_KEYS.map((key) => (
            <button
              key={key}
              onClick={() => handlePresetChange(key)}
              className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                config.providerName === key
                  ? 'border-zinc-900 bg-zinc-900 text-white dark:border-zinc-50 dark:bg-zinc-50 dark:text-zinc-900'
                  : 'border-zinc-200 bg-white text-zinc-600 hover:border-zinc-300 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400'
              }`}
            >
              {key === 'custom' ? t('smtp.custom') : (presets[key]?.name || key.toUpperCase())}
            </button>
          ))}
        </div>
      </div>

      {/* SMTP settings */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label className="mb-1 text-xs">{t('smtp.smtpHost')}</Label>
          <Input
            value={config.smtpHost}
            onChange={(e) => setConfig((p) => ({ ...p, smtpHost: e.target.value }))}
            placeholder="smtp.qq.com"
            className="h-8 text-xs"
          />
        </div>
        <div>
          <Label className="mb-1 text-xs">{t('smtp.smtpPort')}</Label>
          <Input
            type="number"
            value={config.smtpPort}
            onChange={(e) => setConfig((p) => ({ ...p, smtpPort: parseInt(e.target.value) || 587 }))}
            className="h-8 text-xs"
          />
        </div>
        <div>
          <Label className="mb-1 text-xs">{t('smtp.username')}</Label>
          <Input
            value={config.smtpUser}
            onChange={(e) => setConfig((p) => ({ ...p, smtpUser: e.target.value }))}
            placeholder="your@email.com"
            className="h-8 text-xs"
          />
        </div>
        <div>
          <Label className="mb-1 text-xs">{t('smtp.password')}</Label>
          <Input
            type="password"
            value={config.smtpPassword || ''}
            onChange={(e) => setConfig((p) => ({ ...p, smtpPassword: e.target.value }))}
            placeholder={existingConfig ? '••••••••' : t('smtp.passwordPlaceholder')}
            className="h-8 text-xs"
          />
        </div>
        <div>
          <Label className="mb-1 text-xs">{t('smtp.imapHost')}</Label>
          <Input
            value={config.imapHost || ''}
            onChange={(e) => setConfig((p) => ({ ...p, imapHost: e.target.value }))}
            placeholder="imap.qq.com"
            className="h-8 text-xs"
          />
        </div>
        <div>
          <Label className="mb-1 text-xs">{t('smtp.imapPort')}</Label>
          <Input
            type="number"
            value={config.imapPort}
            onChange={(e) => setConfig((p) => ({ ...p, imapPort: parseInt(e.target.value) || 993 }))}
            className="h-8 text-xs"
          />
        </div>
        <div className="col-span-2">
          <Label className="mb-1 text-xs">{t('smtp.fromName')}</Label>
          <Input
            value={config.fromName || ''}
            onChange={(e) => setConfig((p) => ({ ...p, fromName: e.target.value }))}
            placeholder={t('smtp.fromNamePlaceholder')}
            className="h-8 text-xs"
          />
        </div>
      </div>

      {/* Test result */}
      {testResult && (
        <div className="mt-3 rounded-md border p-3 text-xs">
          <div className="flex items-center gap-2">
            {testResult.smtpOk ? (
              <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
            ) : (
              <XCircle className="h-3.5 w-3.5 text-red-500" />
            )}
            <span>SMTP: {testResult.smtpOk ? t('smtp.testSuccess') : testResult.smtpError}</span>
          </div>
          <div className="mt-1 flex items-center gap-2">
            {testResult.imapOk ? (
              <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
            ) : (
              <XCircle className="h-3.5 w-3.5 text-red-500" />
            )}
            <span>IMAP: {testResult.imapOk ? t('smtp.testSuccess') : testResult.imapError}</span>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 flex items-center gap-2">
        <Button
          onClick={handleSave}
          disabled={saving || !config.smtpHost || !config.smtpUser || !config.smtpPassword}
          loading={saving}
          loadingText={t('smtp.save')}
          size="sm"
          className="h-8 text-xs"
        >
          {t('smtp.save')}
        </Button>
        {existingConfig && (
          <Button
            onClick={handleTest}
            loading={testing}
            loadingText={t('smtp.testConnection')}
            variant="outline"
            size="sm"
            className="h-8 text-xs"
          >
            {t('smtp.testConnection')}
          </Button>
        )}
        {existingConfig && (
          <Button onClick={handleDelete} variant="ghost" size="sm" className="h-8 text-xs text-red-500 hover:text-red-600">
            <Trash2 className="mr-1 h-3 w-3" />
            {t('smtp.delete')}
          </Button>
        )}
        {saveStatus === 'success' && (
          <span className="text-xs text-emerald-600">{t('smtp.saved')}</span>
        )}
      </div>
    </div>
  )
}
