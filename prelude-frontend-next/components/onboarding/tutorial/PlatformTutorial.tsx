import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X,
  ChevronLeft,
  ChevronRight,
  Check,
  Lightbulb,
  MousePointerClick,
  ArrowRight,
  Sparkles,
} from 'lucide-react'

// Tutorial modules separated by feature area
export const tutorialModules = {
  dashboard: {
    id: 'dashboard',
    name: 'Dashboard & Navigation',
    description: 'Learn how to navigate the platform and use the dashboard',
    icon: '📊',
    steps: [
      {
        id: 'welcome',
        title: 'Welcome to Prelude Platform!',
        description:
          "Let's take a quick tour of the main navigation and dashboard. Follow the highlighted areas and click where indicated.",
        targetSelector: null,
        position: 'center',
        action: 'Click "Next" to begin the tour',
      },
      {
        id: 'sidebar',
        title: 'Navigation Sidebar',
        description:
          'This sidebar is your main navigation hub. All major features are accessible from here.',
        targetSelector: '.sidebar-menu',
        position: 'right',
        action: 'Notice the different sections: Overview, Business, and Team & Calendar',
      },
      {
        id: 'dashboard-link',
        title: 'Dashboard - Your Command Center',
        description:
          'The Dashboard shows your key metrics, tasks, and AI agent status at a glance.',
        targetSelector: '[data-view="dashboard"]',
        position: 'right',
        action: 'Click the Dashboard menu item',
        requireClick: true,
        clickTarget: '[data-view="dashboard"]',
      },
      {
        id: 'ai-assistant',
        title: 'AI Assistant',
        description:
          'Your AI Assistant is always available to help with tasks, answer questions, and schedule meetings.',
        targetSelector: '.sidebar-menu',
        position: 'right',
        action: 'Look at the bottom of the sidebar for the AI Assistant status',
        focusBottom: true,
      },
      {
        id: 'user-menu',
        title: 'User Profile & Settings',
        description: 'Access your profile, settings, and logout from the user menu at the bottom.',
        targetSelector: '.sidebar-menu',
        position: 'right',
        action: 'Your user profile is at the bottom of the sidebar',
        focusBottom: true,
      },
    ],
  },
  leads: {
    id: 'leads',
    name: 'Lead Generation',
    description: 'Discover how to generate and manage leads',
    icon: '👥',
    steps: [
      {
        id: 'leads-intro',
        title: 'Lead Generation Overview',
        description:
          'The Lead Generation module helps you discover new business opportunities from LinkedIn, Apollo.io, and other sources.',
        targetSelector: null,
        position: 'center',
        action: "Let's explore the lead generation features",
      },
      {
        id: 'leads-nav',
        title: 'Navigate to Lead Generation',
        description: 'Click here to access the Lead Generation module.',
        targetSelector: '[data-view="leads"]',
        position: 'right',
        action: 'Click "Lead Generation" to open the module',
        requireClick: true,
        clickTarget: '[data-view="leads"]',
      },
      {
        id: 'leads-features',
        title: 'Lead Generation Features',
        description:
          'In Lead Generation, you can:\n• Search LinkedIn for prospects\n• Import leads from Apollo.io\n• Analyze market density with Google Maps\n• Organize leads in workflows\n• Export lead data',
        targetSelector: null,
        position: 'center',
        action: 'Explore the various lead generation tools available',
      },
      {
        id: 'leads-workflow',
        title: 'Lead Workflows',
        description:
          'Organize your leads into different workflow stages to track your prospecting process.',
        targetSelector: null,
        position: 'center',
        action: 'Use workflows to manage your lead pipeline effectively',
      },
    ],
  },
  crm: {
    id: 'crm',
    name: 'Customer Relations (CRM)',
    description: 'Master customer relationship management',
    icon: '❤️',
    steps: [
      {
        id: 'crm-intro',
        title: 'CRM Overview',
        description:
          'The CRM helps you manage all customer relationships, track interactions, and maintain strong connections with your clients.',
        targetSelector: null,
        position: 'center',
        action: "Let's explore the CRM features",
      },
      {
        id: 'crm-nav',
        title: 'Navigate to CRM',
        description: 'Access the Customer Relations module from the sidebar.',
        targetSelector: '[data-view="crm"]',
        position: 'right',
        action: 'Click "Customer Relations" to open the CRM',
        requireClick: true,
        clickTarget: '[data-view="crm"]',
      },
      {
        id: 'crm-features',
        title: 'CRM Capabilities',
        description:
          'Key CRM features:\n• View and search all customers\n• Generate AI-powered email templates\n• Track customer interaction history\n• Analyze customer insights\n• Export customer data\n• Assign customers to team members',
        targetSelector: null,
        position: 'center',
        action: 'Use these features to manage customer relationships',
      },
      {
        id: 'crm-ai-email',
        title: 'AI Email Generation',
        description:
          'The CRM includes AI-powered email generation to help you craft professional, personalized messages to your customers.',
        targetSelector: null,
        position: 'center',
        action: 'Try the AI email generator for quick, effective communication',
      },
    ],
  },
  onboarding: {
    id: 'onboarding',
    name: 'User Onboarding',
    description: 'Setup your team and understand the onboarding process',
    icon: '🎓',
    steps: [
      {
        id: 'onboarding-intro',
        title: 'User Onboarding Overview',
        description:
          'The User Onboarding section helps you manage your team and track system setup progress.',
        targetSelector: null,
        position: 'center',
        action: "Let's explore the onboarding features",
      },
      {
        id: 'onboarding-nav',
        title: 'Navigate to User Onboarding',
        description: 'Access team management and personal onboarding from here.',
        targetSelector: '[data-view="user-onboarding"]',
        position: 'right',
        action: 'Click "User Onboarding" to open the module',
        requireClick: true,
        clickTarget: '[data-view="user-onboarding"]',
      },
      {
        id: 'onboarding-tabs',
        title: 'Two Main Sections',
        description:
          'User Onboarding has two tabs:\n• Team Organization: Invite and manage team members\n• Personal Onboarding: Track database setup and system status',
        targetSelector: null,
        position: 'center',
        action: 'Switch between tabs to access different features',
      },
      {
        id: 'team-org',
        title: 'Team Organization',
        description:
          'In Team Organization, you can:\n• View your account information\n• Invite new team members\n• Assign roles (Admin, Manager, User, Viewer)\n• Set access levels (1-10)\n• View all team members',
        targetSelector: null,
        position: 'center',
        action: 'Use this to build and manage your team',
      },
      {
        id: 'personal-onboarding',
        title: 'Personal Onboarding',
        description:
          'The Personal Onboarding tab shows:\n• Database setup progress\n• Table checklist\n• Completion percentage\n• System initialization status',
        targetSelector: null,
        position: 'center',
        action: 'Monitor your system setup progress here',
      },
    ],
  },
}

interface TutorialStep {
  id: string
  title: string
  description: string
  targetSelector?: string | null
  position?: string
  action?: string
  requireClick?: boolean
  clickTarget?: string
  focusBottom?: boolean
}

interface TutorialModule {
  id: string
  name: string
  description: string
  icon: string
  steps: TutorialStep[]
}

interface PlatformTutorialProps {
  isOpen: boolean
  onClose: () => void
  tutorialType?: string
  onNavigate?: (viewId: string) => void
}

function PlatformTutorial({
  isOpen,
  onClose,
  tutorialType = 'dashboard',
  onNavigate,
}: PlatformTutorialProps) {
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [spotlightRect, setSpotlightRect] = useState<any>(null)
  const [isTransitioning, setIsTransitioning] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)

  const currentModule = tutorialModules[tutorialType as keyof typeof tutorialModules]
  const currentStep = currentModule?.steps[currentStepIndex]
  const totalSteps = currentModule?.steps.length || 0
  const progress = Math.round(((currentStepIndex + 1) / totalSteps) * 100)

  // Calculate spotlight position
  useEffect(() => {
    if (!isOpen || !currentStep) return

    const updateSpotlight = () => {
      if (currentStep.targetSelector) {
        const element = document.querySelector(currentStep.targetSelector)
        if (element) {
          const rect = element.getBoundingClientRect()

          // Add padding around the element
          const padding = 16
          setSpotlightRect({
            top: rect.top - padding,
            left: rect.left - padding,
            width: rect.width + padding * 2,
            height: rect.height + padding * 2,
            originalRect: rect,
          })
        } else {
          setSpotlightRect(null)
        }
      } else {
        setSpotlightRect(null)
      }
    }

    // Initial update
    updateSpotlight()

    // Update on scroll or resize
    window.addEventListener('scroll', updateSpotlight, true)
    window.addEventListener('resize', updateSpotlight)

    return () => {
      window.removeEventListener('scroll', updateSpotlight, true)
      window.removeEventListener('resize', updateSpotlight)
    }
  }, [isOpen, currentStep, currentStepIndex])

  const handleFinish = useCallback(() => {
    onClose()
    setCurrentStepIndex(0)
  }, [onClose])

  const handleNext = useCallback(() => {
    if (currentStepIndex < totalSteps - 1) {
      setIsTransitioning(true)
      setTimeout(() => {
        setCurrentStepIndex((prev) => prev + 1)
        setIsTransitioning(false)
      }, 200)
    } else {
      handleFinish()
    }
  }, [currentStepIndex, totalSteps, handleFinish])

  // Handle element clicks if required
  useEffect(() => {
    if (!isOpen || !currentStep?.requireClick) return

    const handleClick = (e: any) => {
      const target = e.target.closest(currentStep.clickTarget)
      if (target) {
        e.preventDefault()
        e.stopPropagation()
        // Small delay to show the click, then advance
        setTimeout(() => {
          handleNext()
        }, 300)
      }
    }

    document.addEventListener('click', handleClick, true)

    return () => {
      document.removeEventListener('click', handleClick, true)
    }
  }, [isOpen, currentStep, currentStepIndex, handleNext])

  const handlePrevious = () => {
    if (currentStepIndex > 0) {
      setIsTransitioning(true)
      setTimeout(() => {
        setCurrentStepIndex((prev) => prev - 1)
        setIsTransitioning(false)
      }, 200)
    }
  }

  const handleSkip = () => {
    if (window.confirm(`Skip the ${currentModule.name} tutorial? You can restart it anytime.`)) {
      onClose()
      setCurrentStepIndex(0)
    }
  }

  // Calculate instruction card position
  const getInstructionPosition = () => {
    if (!spotlightRect) {
      return { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }
    }

    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight
    const cardWidth = 400
    const cardHeight = 250
    const spacing = 24

    let position: any = {}

    // Try to position based on currentStep.position preference
    switch (currentStep.position) {
      case 'right':
        // Position to the right of the spotlight
        if (spotlightRect.left + spotlightRect.width + cardWidth + spacing < viewportWidth) {
          position = {
            top: spotlightRect.top + spotlightRect.height / 2,
            left: spotlightRect.left + spotlightRect.width + spacing,
            transform: 'translateY(-50%)',
          }
        } else {
          // Fallback to bottom
          position = {
            top: spotlightRect.top + spotlightRect.height + spacing,
            left: Math.max(
              spacing,
              Math.min(viewportWidth - cardWidth - spacing, spotlightRect.left)
            ),
          }
        }
        break
      case 'left':
        if (spotlightRect.left - cardWidth - spacing > 0) {
          position = {
            top: spotlightRect.top + spotlightRect.height / 2,
            left: spotlightRect.left - cardWidth - spacing,
            transform: 'translateY(-50%)',
          }
        } else {
          position = {
            top: spotlightRect.top + spotlightRect.height + spacing,
            left: Math.max(
              spacing,
              Math.min(viewportWidth - cardWidth - spacing, spotlightRect.left)
            ),
          }
        }
        break
      case 'bottom':
        position = {
          top: spotlightRect.top + spotlightRect.height + spacing,
          left: Math.max(
            spacing,
            Math.min(viewportWidth - cardWidth - spacing, spotlightRect.left)
          ),
        }
        break
      case 'top':
        position = {
          bottom: viewportHeight - spotlightRect.top + spacing,
          left: Math.max(
            spacing,
            Math.min(viewportWidth - cardWidth - spacing, spotlightRect.left)
          ),
        }
        break
      default:
        position = {
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
        }
    }

    return position
  }

  if (!isOpen || !currentModule) return null

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Dark overlay with SVG cutout for spotlight */}
          <motion.div
            ref={overlayRef}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="pointer-events-none fixed inset-0 z-[200]"
            style={{ isolation: 'isolate' }}
          >
            <svg className="absolute inset-0 h-full w-full" style={{ pointerEvents: 'none' }}>
              <defs>
                <mask id="spotlight-mask">
                  <rect x="0" y="0" width="100%" height="100%" fill="white" />
                  {spotlightRect && (
                    <rect
                      x={spotlightRect.left}
                      y={spotlightRect.top}
                      width={spotlightRect.width}
                      height={spotlightRect.height}
                      rx="12"
                      fill="black"
                    />
                  )}
                </mask>
              </defs>
              <rect
                x="0"
                y="0"
                width="100%"
                height="100%"
                fill="rgba(0, 0, 0, 0.75)"
                mask="url(#spotlight-mask)"
              />
            </svg>

            {/* Glowing border around spotlight */}
            {spotlightRect && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3 }}
                className="absolute rounded-xl border-4 border-rule shadow-2xl"
                style={{
                  top: spotlightRect.top,
                  left: spotlightRect.left,
                  width: spotlightRect.width,
                  height: spotlightRect.height,
                  boxShadow:
                    '0 0 0 4px rgba(161, 161, 170, 0.3), 0 0 40px rgba(161, 161, 170, 0.5)',
                  pointerEvents: currentStep.requireClick ? 'none' : 'auto',
                }}
              />
            )}

            {/* Animated pointer arrow */}
            {spotlightRect && currentStep.requireClick && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{
                  opacity: [0.5, 1, 0.5],
                  x: [-10, 0, -10],
                }}
                transition={{
                  duration: 1.5,
                  repeat: Infinity,
                  ease: 'easeInOut',
                }}
                className="absolute"
                style={{
                  top: spotlightRect.top + spotlightRect.height / 2 - 12,
                  left: spotlightRect.left - 40,
                  pointerEvents: 'none',
                }}
              >
                <ArrowRight className="h-6 w-6 text-mute" />
              </motion.div>
            )}
          </motion.div>

          {/* Instruction Card */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{
              opacity: isTransitioning ? 0 : 1,
              scale: isTransitioning ? 0.9 : 1,
            }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.2 }}
            className="pointer-events-auto fixed z-[201] w-full max-w-md rounded-2xl bg-bone shadow-2xl"
            style={getInstructionPosition()}
          >
            {/* Header */}
            <div className="relative rounded-t-2xl bg-deep p-5">
              <button
                onClick={handleSkip}
                className="absolute top-3 right-3 rounded-lg p-1.5 text-bone transition-colors hover:bg-bone/20"
                title="Skip Tutorial"
              >
                <X className="h-4 w-4" />
              </button>

              <div className="pr-8">
                <div className="mb-2 flex items-center gap-2">
                  <span className="text-2xl">{currentModule.icon}</span>
                  <span className="text-xs font-medium tracking-wider text-bone/90 uppercase">
                    {currentModule.name} • Step {currentStepIndex + 1}/{totalSteps}
                  </span>
                </div>
                <h3 className="mb-2 text-xl font-bold text-bone">{currentStep.title}</h3>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-bone/20">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    className="h-full rounded-full bg-bone"
                    transition={{ duration: 0.3 }}
                  />
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="space-y-4 p-5">
              <p className="leading-relaxed whitespace-pre-line text-ink">
                {currentStep.description}
              </p>

              {currentStep.action && (
                <div className="flex items-start gap-3 rounded-xl border border-rule bg-paper p-3">
                  <MousePointerClick className="mt-0.5 h-5 w-5 flex-shrink-0 text-deep" />
                  <div className="flex-1">
                    <p className="mb-1 text-sm font-medium text-deep">
                      {currentStep.requireClick ? 'Click to Continue' : 'Next Step'}
                    </p>
                    <p className="text-sm text-ink">{currentStep.action}</p>
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between rounded-b-2xl border-t border-rule bg-paper p-5">
              <button
                onClick={handlePrevious}
                disabled={currentStepIndex === 0}
                className="flex items-center gap-2 rounded-lg px-4 py-2 text-ink transition-colors hover:bg-cream disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </button>

              <div className="flex items-center gap-1">
                {currentModule.steps.map((_, index) => (
                  <div
                    key={index}
                    className={`h-1.5 rounded-full transition-all ${
                      index === currentStepIndex
                        ? 'w-6 bg-deep'
                        : index < currentStepIndex
                          ? 'w-1.5 bg-mute'
                          : 'w-1.5 bg-fog'
                    }`}
                  />
                ))}
              </div>

              {!currentStep.requireClick &&
                (currentStepIndex < totalSteps - 1 ? (
                  <button
                    onClick={handleNext}
                    className="flex items-center gap-2 rounded-lg bg-deep px-5 py-2 font-medium text-bone shadow-md transition-all hover:bg-deep/90 hover:shadow-lg"
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </button>
                ) : (
                  <button
                    onClick={handleFinish}
                    className="flex items-center gap-2 rounded-lg bg-accent px-5 py-2 font-medium text-bone shadow-md transition-all hover:bg-accent/90 hover:shadow-lg"
                  >
                    <Check className="h-4 w-4" />
                    Finish
                  </button>
                ))}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

export default PlatformTutorial
