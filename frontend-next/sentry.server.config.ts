import * as Sentry from '@sentry/nextjs'

Sentry.init({
  dsn: 'https://e2a07a1610327287bf7b92e8df014936@o4511067702820864.ingest.us.sentry.io/4511067705311232',
  tracesSampleRate: 0.1,

  beforeSend(event) {
    // Drop ENOENT errors from webpack chunk loading during dev hot reload
    if (
      process.env.NODE_ENV === 'development' &&
      event.exception?.values?.some((e) => e.type === 'Error' && e.value?.includes('ENOENT'))
    ) {
      return null
    }
    return event
  },
})
