import * as Sentry from '@sentry/nextjs'

Sentry.init({
  dsn: 'https://e2a07a1610327287bf7b92e8df014936@o4511067702820864.ingest.us.sentry.io/4511067705311232',
  tracesSampleRate: 0.1,

  beforeSend(event) {
    // Drop unhandled promise rejections with no stacktrace (browser resource load noise)
    if (
      event.exception?.values?.some(
        (e) => !e.stacktrace?.frames?.length && e.mechanism?.type === 'onunhandledrejection'
      )
    ) {
      return null
    }
    return event
  },
})
