'use client'

import React, { useState, useCallback, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useRouter, usePathname } from '@/i18n/navigation'
import { useSearchParams } from 'next/navigation'
import Image from 'next/image'

import {
  PanelLeftClose,
  ChevronRight,
  LogOut,
  Lock,
  Sun,
  Moon,
  Users,
  Swords,
  Sparkles,
  Handshake,
  Mail,
  Settings,
  Store,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { toast } from 'sonner'

import { useTranslations, useLocale } from 'next-intl'
import { useAuth } from '@/hooks/useAuth'
import { useSubscription } from '@/stores/subscriptionStore'
import { useSidebarStore } from '@/stores/sidebarStore'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import NotificationCenter from '@/components/layout/NotificationCenter'

// Types for navigation structure
interface NavSubtab {
  id: string
  label: string
  route: string // full route path like '/leads?tab=lead-management'
}

interface NavItem {
  id: string
  label: string
  icon: LucideIcon // required — collapsed sidebar renders icons only
  route?: string // for flat items (no subtabs)
  subtabs?: NavSubtab[]
  requiresPaid?: boolean
}

interface NavSection {
  id: string
  header?: string // section header text (e.g. "MARKET (市场)")
  items: NavItem[]
}

const NON_WORKSPACE_ROUTES = ['/two-pager']

function useNavigationSections(): NavSection[] {
  const t = useTranslations('navigation')
  const locale = useLocale()

  return useMemo(() => {
    const sections: NavSection[] = [
      // MARKET section
      {
        id: 'market',
        header: `${t('sections.market')}`,
        items: [
          {
            id: 'buyers',
            label: t('items.buyers'),
            icon: Users,
            route: '/leads?tab=lead-management',
          },
          {
            id: 'competitors',
            label: t('items.competitors'),
            icon: Swords,
            route: '/leads?tab=competitors',
          },
        ],
      },
      // PIPELINE section
      {
        id: 'pipeline',
        header: `${t('sections.pipeline')}`,
        items: [
          {
            id: 'my-leads',
            label: t('items.myLeads'),
            icon: Sparkles,
            route: '/crm',
            requiresPaid: true,
          },
          {
            id: 'deal-rooms',
            label: t('items.dealRooms'),
            icon: Handshake,
            route: '/deals',
            requiresPaid: true,
          },
          {
            id: 'storefront',
            label: t('items.storefront'),
            icon: Store,
            route: '/storefront',
          },
        ],
      },
      // Outreach (flat, no section header)
      {
        id: 'outreach',
        items: [
          {
            id: 'outreach',
            label: t('items.outreach'),
            icon: Mail,
            route: '/leads?tab=campaigns',
            requiresPaid: true,
          },
        ],
      },
      // Settings (expandable with subtabs)
      {
        id: 'settings-section',
        items: [
          {
            id: 'settings',
            label: t('items.settings'),
            icon: Settings,
            subtabs: [
              {
                id: 'factory-profile',
                label: t('subtabs.factoryProfile'),
                route: '/user-onboarding?tab=customize-ai',
              },
              {
                id: 'team-invitations',
                label: t('subtabs.teamInvitations'),
                route: '/user-onboarding?tab=team-organization',
              },
              {
                id: 'email-profile',
                label: t('subtabs.emailProfile'),
                route: '/profiles?tab=preferences',
              },
              {
                id: 'email-templates',
                label: t('subtabs.emailTemplates'),
                route: '/profiles?tab=templates',
              },
            ],
          },
        ],
      },
    ]

    return sections
  }, [t, locale])
}

// Default tabs for pages that have tab-based routing
const DEFAULT_TABS: Record<string, string> = {
  '/leads': 'lead-management',
  '/profiles': 'templates',
  '/user-onboarding': 'team-organization',
}

function isRouteActive(
  itemRoute: string,
  pathname: string,
  searchParams: URLSearchParams | null,
  workspaceId: string
): boolean {
  const [routePath, routeQuery] = itemRoute.split('?')
  const isAbsolute = NON_WORKSPACE_ROUTES.some(route => routePath.startsWith(route))

  const pathSuffix = isAbsolute
    ? routePath
    : `/workspace/${workspaceId}${routePath}`
  if (!pathname?.endsWith(pathSuffix)) return false

  if (routeQuery) {
    const [key, value] = routeQuery.split('=')
    const currentValue = searchParams?.get(key)
    const effectiveValue = currentValue ?? DEFAULT_TABS[routePath]
    return effectiveValue === value
  }

  return !searchParams?.get('tab')
}

interface FlatNavItemProps {
  item: NavItem
  isActive: boolean
  isCollapsed: boolean
  disabled?: boolean
  onClick: () => void
}

const FlatNavItem = React.memo<FlatNavItemProps>(({ item, isActive, isCollapsed, disabled, onClick }) => {
  const t = useTranslations('navigation')
  const Icon = item.icon
  const handleClick = () => {
    if (disabled) {
      toast(t('upgrade.toast', { feature: item.label }), {
        description: t('upgrade.description'),
        action: {
          label: t('upgrade.action'),
          onClick: () => window.open('mailto:sales@prelude.so?subject=Upgrade%20Plan'),
        },
      })
      return
    }
    onClick()
  }

  return (
    <button
      onClick={handleClick}
      aria-current={isActive ? 'page' : undefined}
      title={isCollapsed ? item.label : undefined}
      className={`relative flex w-full items-center gap-2.5 text-left text-[13.5px] transition-colors duration-150 ${
        isCollapsed ? 'justify-center py-2.5' : 'py-2 pl-[18px] pr-3'
      } ${
        disabled
          ? 'cursor-not-allowed text-ink/60'
          : isActive
            ? 'bg-cream font-medium text-deep'
            : 'text-ink hover:bg-cream'
      }`}
    >
      {isActive && !disabled && (
        <span
          aria-hidden
          className="absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-r-sm bg-accent"
        />
      )}
      {isCollapsed ? (
        <Icon
          className={`h-[18px] w-[18px] ${isActive ? 'text-deep' : 'text-mute'} ${disabled ? 'opacity-50' : ''}`}
          strokeWidth={1.5}
          aria-hidden
        />
      ) : (
        <span className="flex min-w-0 flex-1 items-center gap-1.5 truncate">
          {item.label}
          {disabled && <Lock className="h-3 w-3 flex-shrink-0 text-mute" />}
        </span>
      )}
    </button>
  )
})
FlatNavItem.displayName = 'FlatNavItem'

interface ExpandableNavItemProps {
  item: NavItem
  isCollapsed: boolean
  activeSubtabId: string | null
  onSubtabClick: (route: string) => void
}

const ExpandableNavItem = React.memo<ExpandableNavItemProps>(
  ({ item, isCollapsed, activeSubtabId, onSubtabClick }) => {
    const [isExpanded, setIsExpanded] = useState(false)
    const hasActiveSubtab = item.subtabs?.some((s) => s.id === activeSubtabId) ?? false
    const Icon = item.icon

    // Auto-expand if a subtab is active
    useEffect(() => {
      if (hasActiveSubtab) {
        setIsExpanded(true)
      }
    }, [hasActiveSubtab])

    // In collapsed mode, clicking a subtab-parent just navigates to its first
    // subtab — there's nowhere to expand to visually.
    const handleClick = () => {
      if (isCollapsed && item.subtabs?.[0]) {
        onSubtabClick(item.subtabs[0].route)
        return
      }
      setIsExpanded(!isExpanded)
    }

    return (
      <div>
        <button
          onClick={handleClick}
          aria-current={hasActiveSubtab ? 'page' : undefined}
          title={isCollapsed ? item.label : undefined}
          className={`relative flex w-full items-center gap-2.5 text-left text-[13.5px] transition-colors duration-150 ${
            isCollapsed ? 'justify-center py-2.5' : 'py-2 pl-[18px] pr-3'
          } ${hasActiveSubtab ? 'bg-cream font-medium text-deep' : 'text-ink hover:bg-cream'}`}
        >
          {hasActiveSubtab && (
            <span
              aria-hidden
              className="absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-r-sm bg-accent"
            />
          )}
          {isCollapsed ? (
            <Icon
              className={`h-[18px] w-[18px] ${hasActiveSubtab ? 'text-deep' : 'text-mute'}`}
              strokeWidth={1.5}
              aria-hidden
            />
          ) : (
            <>
              <span className="min-w-0 flex-1 truncate">{item.label}</span>
              <ChevronRight
                className={`h-3 w-3 flex-shrink-0 text-mute transition-transform duration-200 ${
                  isExpanded ? 'rotate-90' : ''
                }`}
              />
            </>
          )}
        </button>

        <AnimatePresence>
          {isExpanded && !isCollapsed && item.subtabs && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              {item.subtabs.map((subtab) => {
                const isActiveSubtab = subtab.id === activeSubtabId
                return (
                  <button
                    key={subtab.id}
                    onClick={() => onSubtabClick(subtab.route)}
                    aria-current={isActiveSubtab ? 'page' : undefined}
                    className={`flex w-full items-center py-1.5 pl-[34px] pr-3 text-left text-[12.5px] transition-colors duration-150 ${
                      isActiveSubtab ? 'bg-cream text-deep font-medium' : 'text-mute hover:bg-cream hover:text-ink'
                    }`}
                  >
                    <span className="min-w-0 flex-1 truncate">{subtab.label}</span>
                  </button>
                )
              })}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    )
  }
)
ExpandableNavItem.displayName = 'ExpandableNavItem'

interface SidebarMenuProps {
  className?: string
}

export default function SidebarMenu({ className = '' }: SidebarMenuProps) {
  const { user, logout } = useAuth()
  const { isSidebarCollapsed, setIsSidebarCollapsed } = useSidebarStore()
  const { workspaceId } = useWorkspace()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const t = useTranslations('navigation')
  const locale = useLocale()
  const sections = useNavigationSections()
  const router = useRouter()
  const { fetchSubscription } = useSubscription()

  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  useEffect(() => {
    if (typeof document !== 'undefined') {
      const current = (document.documentElement.dataset.theme as 'light' | 'dark') || 'light'
      setTheme(current)
    }
  }, [])

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    try {
      localStorage.setItem('prelude-theme', next)
    } catch {
      // ignore — private mode, full disk, etc.
    }
    setTheme(next)
  }

  useEffect(() => {
    fetchSubscription()
  }, [fetchSubscription])

  const navigateTo = useCallback(
    (route: string) => {
      const [path, query] = route.split('?')
      const isAbsolute = NON_WORKSPACE_ROUTES.some(r => path.startsWith(r))
      const fullPath = isAbsolute
        ? `${path}${query ? `?${query}` : ''}`
        : `/workspace/${workspaceId}${path}${query ? `?${query}` : ''}`
      router.push(fullPath)
    },
    [router, workspaceId]
  )

  const getActiveItemId = useCallback(
    (item: NavItem): boolean => {
      if (!item.route) return false
      return isRouteActive(item.route, pathname, searchParams, workspaceId)
    },
    [pathname, searchParams, workspaceId]
  )

  const getActiveSubtabId = useCallback(
    (item: NavItem): string | null => {
      if (!item.subtabs) return null
      for (const subtab of item.subtabs) {
        if (isRouteActive(subtab.route, pathname, searchParams, workspaceId)) {
          return subtab.id
        }
      }
      return null
    },
    [pathname, searchParams, workspaceId]
  )

  const toggleCollapsed = () => {
    setIsSidebarCollapsed(!isSidebarCollapsed)
  }

  const handleLocaleToggle = () => {
    const nextLocale = locale === 'zh-CN' ? 'en' : 'zh-CN'
    const currentPath = pathname.replace(/^\/(en|zh-CN)/, '')
    const query = searchParams?.toString()
    const newPath = `/${nextLocale}${currentPath}${query ? `?${query}` : ''}`
    window.location.href = newPath
  }

  const initial = user?.name?.charAt(0) || user?.email?.charAt(0) || '?'
  const brandmarkSize = isSidebarCollapsed ? 'h-7 w-7 text-[18px]' : 'h-[22px] w-[22px] text-[15px]'

  return (
    <motion.aside
      initial={{ width: isSidebarCollapsed ? 56 : 220 }}
      animate={{ width: isSidebarCollapsed ? 56 : 220 }}
      transition={{ duration: 0.25, ease: 'easeInOut' }}
      className={`relative flex h-full flex-col overflow-visible border-r border-rule bg-paper ${className}`}
    >
      {/* Header — brandmark (P only) + tools */}
      <div
        className={`flex items-center border-b border-rule ${
          isSidebarCollapsed ? 'flex-col gap-2 py-3' : 'justify-between gap-1.5 py-3 pl-4 pr-3'
        }`}
      >
        <span
          className={`grid flex-shrink-0 place-items-center rounded-[3px] bg-deep ${brandmarkSize}`}
        >
          <span className="-translate-y-[0.5px] font-display leading-none text-bone">P</span>
        </span>
        <div
          className={`flex flex-shrink-0 items-center ${
            isSidebarCollapsed ? 'flex-col gap-1' : 'gap-0.5'
          }`}
        >
          <NotificationCenter />
          <button
            onClick={toggleCollapsed}
            aria-label={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-mute transition-colors hover:bg-cream hover:text-ink"
          >
            <PanelLeftClose
              className={`h-3.5 w-3.5 ${isSidebarCollapsed ? 'rotate-180' : ''}`}
            />
          </button>
        </div>
      </div>

      {/* Navigation */}
      <div className="relative flex-1 overflow-x-visible overflow-y-auto py-2">
        {sections.map((section, i) => (
          <div key={section.id} className={i > 0 && isSidebarCollapsed ? 'mt-1 border-t border-rule pt-1' : 'mb-1'}>
            {section.header && !isSidebarCollapsed && (
              <div className="px-[18px] pt-4 pb-1.5">
                <span className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-mute">
                  {section.header}
                </span>
              </div>
            )}
            {section.items.map((item) => {
              if (item.subtabs && item.subtabs.length > 0) {
                return (
                  <ExpandableNavItem
                    key={item.id}
                    item={item}
                    isCollapsed={isSidebarCollapsed}
                    activeSubtabId={getActiveSubtabId(item)}
                    onSubtabClick={navigateTo}
                  />
                )
              }
              return (
                <FlatNavItem
                  key={item.id}
                  item={item}
                  isActive={getActiveItemId(item)}
                  isCollapsed={isSidebarCollapsed}
                  onClick={() => item.route && navigateTo(item.route)}
                />
              )
            })}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div
        className={`border-t border-rule ${
          isSidebarCollapsed ? 'flex flex-col items-center gap-1.5 py-2.5' : 'flex items-center gap-1.5 px-3 py-2.5'
        }`}
      >
        <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center overflow-hidden rounded-full bg-deep text-[10.5px] font-medium text-bone">
          {user?.picture ? (
            <Image
              src={user.picture}
              alt=""
              width={24}
              height={24}
              className="h-full w-full object-cover"
            />
          ) : (
            <span>{initial}</span>
          )}
        </div>
        {!isSidebarCollapsed && (
          <span className="flex-1 truncate text-[12.5px] text-ink">
            {user?.name || user?.email || 'User'}
          </span>
        )}
        <button
          onClick={toggleTheme}
          aria-label="Toggle theme"
          title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
          className="inline-flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md text-mute transition-colors hover:bg-cream hover:text-ink"
        >
          {theme === 'dark' ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </button>
        {!isSidebarCollapsed && (
          <button
            onClick={handleLocaleToggle}
            title={locale === 'zh-CN' ? 'Switch to English' : '切换到中文'}
            className="flex-shrink-0 rounded border border-rule bg-bone px-1.5 py-[3px] font-mono text-[10px] tracking-[0.08em] text-mute transition-colors hover:border-ink hover:text-ink"
          >
            {locale === 'zh-CN' ? 'EN' : '中'}
          </button>
        )}
        <button
          onClick={logout}
          title={t('signOut')}
          className="inline-flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md text-mute transition-colors hover:bg-threat-lo hover:text-threat"
        >
          <LogOut className="h-3.5 w-3.5" />
        </button>
      </div>
    </motion.aside>
  )
}
