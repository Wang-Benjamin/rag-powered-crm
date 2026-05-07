'use client'

import React from 'react'
import { useTranslations } from 'next-intl'

export default function ChatPage() {
  const t = useTranslations('common.chat')

  return (
    <div className="flex h-full flex-col bg-zinc-50">
      <div className="flex-1 p-6">
        <div className="mx-auto h-full max-w-4xl">
          <div className="mb-6">
            <h1 className="title-page">{t('title')}</h1>
            <p className="mt-1 text-zinc-600">{t('description')}</p>
            <div className="mt-2 flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-zinc-300"></div>
              <span className="text-sm text-zinc-500">{t('comingSoon')}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
