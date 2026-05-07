import React from 'react'
import { motion } from 'framer-motion'
import { X, PlayCircle, CheckCircle } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { tutorialModules } from './PlatformTutorial'

interface TutorialSelectorProps {
  isOpen: boolean
  onClose: () => void
  onSelectTutorial: (tutorialId: string) => void
}

function TutorialSelector({ isOpen, onClose, onSelectTutorial }: TutorialSelectorProps) {
  const t = useTranslations('settings.tutorial')

  if (!isOpen) return null

  const modules = Object.values(tutorialModules)

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[150] flex items-center justify-center bg-black/60 p-6 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        transition={{ type: 'spring', damping: 20 }}
        className="max-h-[80vh] w-full max-w-3xl overflow-hidden rounded-2xl bg-bone shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="relative bg-gradient-to-r from-deep/80 to-deep p-6">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 rounded-lg p-2 text-bone transition-colors hover:bg-bone/20"
          >
            <X className="h-5 w-5" />
          </button>

          <div className="pr-12">
            <h2 className="mb-2 text-2xl font-bold text-bone">{t('title')}</h2>
            <p className="text-sm text-bone/90">{t('subtitle')}</p>
          </div>
        </div>

        {/* Tutorial Options */}
        <div className="max-h-[calc(80vh-140px)] overflow-y-auto p-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {modules.map((module) => (
              <motion.button
                key={module.id}
                onClick={() => {
                  onSelectTutorial(module.id)
                  onClose()
                }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="group relative overflow-hidden rounded-xl border-2 border-rule bg-bone p-5 text-left transition-all hover:border-ink/40 hover:shadow-lg"
              >
                {/* Background Gradient on Hover */}
                <div className="absolute inset-0 bg-gradient-to-br from-paper to-cream opacity-0 transition-opacity group-hover:opacity-100" />

                {/* Content */}
                <div className="relative z-10">
                  <div className="mb-3 flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-4xl">{module.icon}</span>
                      <div>
                        <h3 className="title-block transition-colors">
                          {module.name}
                        </h3>
                        <p className="text-xs text-mute">
                          {t('steps', { count: module.steps.length })}
                        </p>
                      </div>
                    </div>
                    <PlayCircle className="h-6 w-6 flex-shrink-0 text-mute transition-colors group-hover:text-ink" />
                  </div>

                  <p className="text-sm leading-relaxed text-mute">{module.description}</p>

                  {/* Features Preview */}
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
                      <CheckCircle className="h-3 w-3" />
                      {t('interactive')}
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
                      <CheckCircle className="h-3 w-3" />
                      {t('spotlightGuide')}
                    </span>
                  </div>
                </div>
              </motion.button>
            ))}
          </div>

          {/* Help Text */}
          <div className="mt-6 rounded-xl border border-border bg-muted p-4">
            <p className="text-sm text-foreground">
              <strong>Tip:</strong> {t('tip')}
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-rule bg-paper p-6">
          <div className="flex items-center justify-between">
            <p className="text-sm text-mute">{t('exitHint')}</p>
            <button
              onClick={onClose}
              className="rounded-lg px-5 py-2 font-medium text-ink transition-colors hover:bg-cream"
            >
              {t('close')}
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

export default TutorialSelector
