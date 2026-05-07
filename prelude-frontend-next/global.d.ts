import type en from './messages/en/common.json'
import type enCrm from './messages/en/crm.json'
import type enEmail from './messages/en/email.json'
import type enLeads from './messages/en/leads.json'
import type enNav from './messages/en/navigation.json'
import type enAuth from './messages/en/auth.json'
import type enSettings from './messages/en/settings.json'
import type enStorefront from './messages/en/storefront.json'

type Messages = {
  common: typeof en
  crm: typeof enCrm
  email: typeof enEmail
  leads: typeof enLeads
  navigation: typeof enNav
  auth: typeof enAuth
  settings: typeof enSettings
  storefront: typeof enStorefront
}

declare module 'next-intl' {
  interface AppConfig {
    Messages: Messages
  }
}
