import type { Metadata } from 'next'
import { Geist, Instrument_Serif, JetBrains_Mono, Noto_Sans_SC, Noto_Serif_SC } from 'next/font/google'
import { getLocale } from 'next-intl/server'
import './globals.css'

const geist = Geist({
  subsets: ['latin'],
  variable: '--font-geist',
  weight: ['300', '400', '500', '600', '700'],
  display: 'swap',
  preload: false,
})

const instrumentSerif = Instrument_Serif({
  subsets: ['latin'],
  variable: '--font-instrument-serif',
  weight: ['400'],
  style: ['normal', 'italic'],
  display: 'swap',
  preload: false,
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
  weight: ['400', '500'],
  display: 'swap',
  preload: false,
})

const notoSansSC = Noto_Sans_SC({
  weight: ['400', '500', '700'],
  display: 'swap',
  preload: false,
  adjustFontFallback: false,
  variable: '--font-noto-sans-sc',
})

const notoSerifSC = Noto_Serif_SC({
  weight: ['400', '500', '600', '700'],
  display: 'swap',
  preload: false,
  adjustFontFallback: false,
  variable: '--font-noto-serif-sc',
})

export const metadata: Metadata = {
  title: 'Prelude Platform - Business Intelligence & CRM',
  description: 'Comprehensive business intelligence and CRM system with AI capabilities',
  keywords: 'CRM, business intelligence, analytics, lead generation, sales',
  authors: [{ name: 'Prelude Team' }],
}

export const viewport = {
  width: 'device-width',
  initialScale: 1,
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale()

  return (
    <html
      lang={locale}
      data-scroll-behavior="smooth"
      className={`${geist.variable} ${instrumentSerif.variable} ${jetbrainsMono.variable} ${notoSansSC.variable} ${notoSerifSC.variable}`}
      suppressHydrationWarning
    >
      <head>
        {/* Inline theme init — reads localStorage before React hydrates so the user's
            dark/light choice persists across reloads without a flash. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var k='prelude-theme',v=localStorage.getItem(k);var m=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches;var t=(v==='dark'||v==='light')?v:(m?'dark':'light');document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','light');}})();`,
          }}
        />
      </head>
      <body className="font-body antialiased">{children}</body>
    </html>
  )
}
