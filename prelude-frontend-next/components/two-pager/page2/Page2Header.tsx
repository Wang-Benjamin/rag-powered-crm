'use client'

import React from 'react'
import type { TwoPagerData } from '../TwoPagerPage1'

function reportMonth(iso: string): string {
  try {
    const d = new Date(iso)
    return `${d.getUTCFullYear()}年${d.getUTCMonth() + 1}月`
  } catch {
    return ''
  }
}

export interface Page2HeaderProps {
  data: TwoPagerData
}

export default function Page2Header({ data }: Page2HeaderProps) {
  const month = reportMonth(data.generatedAt)

  return (
    <>
      <header className="tp-ph">
        <div className="tp-ph-brand">
          <div className="row1">
            <span className="wm">Prelude</span>
            <span className="zh">璞序</span>
          </div>
          <span className="url">preludeos.com</span>
        </div>
        <div className="tp-ph-meta">
          <div>US Customs · CBP</div>
          <div><b>{month}</b> · 02 / 02</div>
        </div>
      </header>

      <span className="eyebrow">Decision Makers · 决策人 + 开发信</span>
      <h1 className="title">采购负责人 &amp; <em>英文开发信</em></h1>
      <p className="subtitle">每位买家的采购/选品决策人，附已起草的英文开发信初稿 · 可直接发送或修改。</p>
    </>
  )
}
