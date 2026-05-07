'use client'

import React, { useState, useEffect } from 'react'
import { useRouter } from '@/i18n/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ArrowLeft, Check, X, Loader2 } from 'lucide-react'
import { Link } from '@/i18n/navigation'
import { useTranslations } from 'next-intl'
import { syncLocaleFromBackend } from '@/lib/locale'
import { useAuthStore } from '@/stores/authStore'
import { workspacePathFromToken } from '@/lib/auth/tokenUtils'

interface FormData {
  username: string
  password: string
  confirmPassword: string
  email: string
}

// Force dynamic rendering for this page
export const dynamic = 'force-dynamic'

export default function RegisterPage() {
  const router = useRouter()
  const t = useTranslations('auth.register')
  const {
    updateTokens,
    setAuthProvider,
    setIsAuthenticated,
    isAuthenticated,
    initializeFromStorage,
  } = useAuthStore()

  const [formData, setFormData] = useState<FormData>({
    username: '',
    password: '',
    confirmPassword: '',
    email: '',
  })
  const [includeEmail, setIncludeEmail] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null)
  const [checkingUsername, setCheckingUsername] = useState(false)

  // Initialize auth state from localStorage on mount
  useEffect(() => {
    initializeFromStorage()
  }, [initializeFromStorage])

  // Redirect if already authenticated
  useEffect(() => {
    // Check both store state and localStorage for token presence
    const idToken = localStorage.getItem('id_token')
    if (isAuthenticated || idToken) {
      if (idToken) {
        const path = workspacePathFromToken(idToken)
        if (path) {
          router.push(path)
        } else {
          console.error('Error parsing token')
          router.push('/login')
        }
      }
    }
  }, [isAuthenticated, router])

  // Debounced username availability check
  useEffect(() => {
    if (formData.username.length >= 3) {
      const timeoutId = setTimeout(async () => {
        setCheckingUsername(true)
        try {
          const response = await fetch(
            `/api/proxy/settings/auth/check-username?username=${encodeURIComponent(formData.username)}`,
            { method: 'POST' }
          )
          const data = await response.json()
          setUsernameAvailable(data.available)
        } catch (error) {
          console.error('Error checking username:', error)
          setUsernameAvailable(null)
        } finally {
          setCheckingUsername(false)
        }
      }, 500)

      return () => clearTimeout(timeoutId)
    } else {
      setUsernameAvailable(null)
    }
  }, [formData.username])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const validateForm = (): string | null => {
    if (formData.username.length < 3) return t('usernameTooShort')
    if (formData.username.includes('@')) return t('usernameNoAt')
    if (formData.password.length < 8) return t('passwordTooShort')
    if (formData.password !== formData.confirmPassword) return t('passwordsNoMatch')
    if (includeEmail && formData.email && !formData.email.includes('@')) return t('invalidEmail')
    if (usernameAvailable === false) return t('usernameTaken')
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const validationError = validateForm()
    if (validationError) {
      setError(validationError)
      return
    }

    setLoading(true)

    try {
      const requestBody: any = {
        username: formData.username.trim(),
        password: formData.password,
        confirm_password: formData.confirmPassword,
      }

      // Only include email if checkbox is checked and email is provided
      if (includeEmail && formData.email) {
        requestBody.email = formData.email.trim()
      }

      const response = await fetch('/api/proxy/settings/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      })

      const data = await response.json()

      if (!response.ok) {
        if (response.status === 409) {
          setError(data.detail || t('usernameOrEmailExists'))
        } else if (response.status === 422) {
          setError(data.detail?.[0]?.msg || t('invalidInput'))
        } else {
          setError(data.detail || t('registrationFailed'))
        }
        return
      }

      // Store tokens in Zustand store (convert from backend snake_case)
      updateTokens({
        idToken: data.id_token,
        refreshToken: data.refresh_token,
      })

      setAuthProvider('password')
      setIsAuthenticated(true)

      // Sync locale preference from backend
      syncLocaleFromBackend().catch(() => {})

      // Navigate to workspace CRM
      const path = workspacePathFromToken(data.id_token) ?? '/workspace/default/crm'
      router.push(path)
    } catch (error) {
      console.error('Registration error:', error)
      setError(t('networkError'))
    } finally {
      setLoading(false)
    }
  }

  const passwordsMatch =
    formData.password && formData.confirmPassword && formData.password === formData.confirmPassword

  const getUsernameIcon = () => {
    if (checkingUsername) {
      return (
        <Loader2 className="absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 transform animate-spin text-mute" />
      )
    }
    if (formData.username.length >= 3 && usernameAvailable === true) {
      return (
        <Check className="absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 transform text-accent" />
      )
    }
    if (formData.username.length >= 3 && usernameAvailable === false) {
      return (
        <X className="absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 transform text-threat" />
      )
    }
    return null
  }

  const getPasswordMatchIcon = () => {
    if (formData.confirmPassword && passwordsMatch) {
      return (
        <Check className="absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 transform text-accent" />
      )
    }
    if (formData.confirmPassword && !passwordsMatch) {
      return (
        <X className="absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 transform text-threat" />
      )
    }
    return null
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper p-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="pb-6 text-center">
          <div className="mb-4">
            <h1 className="title-page">{t('platformTitle')}</h1>
            <p className="mt-2 text-ink">{t('platformSubtitle')}</p>
          </div>
          <CardTitle className="title-page">{t('title')}</CardTitle>
          <p className="mt-2 text-sm text-mute">{t('subtitle')}</p>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Link
              href="/login"
              className="mb-4 flex items-center text-sm text-ink transition-colors hover:text-deep"
            >
              <ArrowLeft className="mr-1 h-4 w-4" />
              {t('backToLogin')}
            </Link>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Username */}
            <div className="space-y-2">
              <label htmlFor="username" className="block text-sm font-medium text-ink">
                {t('username')} <span className="text-threat">{t('required')}</span>
              </label>
              <div className="relative">
                <Input
                  id="username"
                  name="username"
                  type="text"
                  value={formData.username}
                  onChange={handleInputChange}
                  required
                  disabled={loading}
                  placeholder={t('usernamePlaceholder')}
                  autoComplete="username"
                  className="h-11 pr-10"
                />
                {getUsernameIcon()}
              </div>
              <p className="text-xs text-mute">{t('usernameHint')}</p>
            </div>

            {/* Password */}
            <div className="space-y-2">
              <label htmlFor="password" className="block text-sm font-medium text-ink">
                {t('password')} <span className="text-threat">{t('required')}</span>
              </label>
              <Input
                id="password"
                name="password"
                type="password"
                value={formData.password}
                onChange={handleInputChange}
                required
                disabled={loading}
                placeholder={t('passwordPlaceholder')}
                autoComplete="new-password"
                className="h-11"
              />
            </div>

            {/* Confirm Password */}
            <div className="space-y-2">
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-ink">
                {t('confirmPassword')} <span className="text-threat">{t('required')}</span>
              </label>
              <div className="relative">
                <Input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  value={formData.confirmPassword}
                  onChange={handleInputChange}
                  required
                  disabled={loading}
                  placeholder={t('confirmPasswordPlaceholder')}
                  autoComplete="new-password"
                  className="h-11 pr-10"
                />
                {getPasswordMatchIcon()}
              </div>
            </div>

            {/* Optional Email Checkbox */}
            <div className="flex items-start space-x-3 rounded-lg border border-rule bg-cream p-4">
              <input
                type="checkbox"
                id="includeEmail"
                checked={includeEmail}
                onChange={(e) => setIncludeEmail(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-rule text-deep focus:ring-accent"
              />
              <label htmlFor="includeEmail" className="flex-1 cursor-pointer text-sm text-ink">
                <span className="font-medium">{t('includeEmail')}</span>
                <p className="mt-1 text-xs text-mute">{t('includeEmailHint')}</p>
              </label>
            </div>

            {/* Email Field (conditional) */}
            {includeEmail && (
              <div className="space-y-2">
                <label htmlFor="email" className="block text-sm font-medium text-ink">
                  {t('email')}
                </label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  disabled={loading}
                  placeholder={t('emailPlaceholder')}
                  autoComplete="email"
                  className="h-11"
                />
                <p className="text-xs text-mute">{t('emailHint')}</p>
              </div>
            )}

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={
                usernameAvailable === false ||
                !passwordsMatch ||
                !formData.username ||
                !formData.password ||
                !formData.confirmPassword
              }
              loading={loading}
              loadingText={t('creatingAccount')}
              className="h-11 w-full"
            >
              {t('createAccount')}
            </Button>

            <p className="text-center text-xs text-mute">
              {t('alreadyHaveAccount')}{' '}
              <Link href="/login" className="font-medium text-foreground hover:underline">
                {t('signInLink')}
              </Link>
            </p>
          </form>

          <div className="mt-6 border-t border-rule pt-4">
            <p className="text-center text-xs text-mute">
              {t('termsNotice')}{' '}
              <a href="#" className="text-foreground hover:underline">
                {t('termsOfService')}
              </a>{' '}
              {t('and')}{' '}
              <a href="#" className="text-foreground hover:underline">
                {t('privacyPolicy')}
              </a>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
