'use client'

import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ChevronDown } from 'lucide-react'

interface Token {
  labelKey: string
  value: string
  descriptionKey: string
}

interface TokenInserterProps {
  onInsertToken: (token: string) => void
  variant?: 'outline' | 'default' | 'ghost'
  size?: 'sm' | 'default' | 'lg'
  className?: string
}

const AVAILABLE_TOKENS: Token[] = [
  {
    labelKey: 'tokenInserter.companyName',
    value: 'name',
    descriptionKey: 'tokenInserter.companyNameDescription',
  },
  {
    labelKey: 'tokenInserter.primaryContact',
    value: 'primary_contact',
    descriptionKey: 'tokenInserter.primaryContactDescription',
  },
  {
    labelKey: 'tokenInserter.email',
    value: 'email',
    descriptionKey: 'tokenInserter.emailDescription',
  },
  {
    labelKey: 'tokenInserter.phone',
    value: 'phone',
    descriptionKey: 'tokenInserter.phoneDescription',
  },
  {
    labelKey: 'tokenInserter.senderName',
    value: 'sender_name',
    descriptionKey: 'tokenInserter.senderNameDescription',
  },
  {
    labelKey: 'tokenInserter.currentDate',
    value: 'current_date',
    descriptionKey: 'tokenInserter.currentDateDescription',
  },
  {
    labelKey: 'tokenInserter.companyWebsite',
    value: 'website',
    descriptionKey: 'tokenInserter.companyWebsiteDescription',
  },
  {
    labelKey: 'tokenInserter.dealValue',
    value: 'deal_value',
    descriptionKey: 'tokenInserter.dealValueDescription',
  },
  {
    labelKey: 'tokenInserter.lastContactDate',
    value: 'last_contact',
    descriptionKey: 'tokenInserter.lastContactDateDescription',
  },
]

export function TokenInserter({
  onInsertToken,
  variant = 'outline',
  size = 'sm',
  className,
}: TokenInserterProps) {
  const t = useTranslations('email')

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant={variant} size={size} className={className}>
          {t('tokenInserter.insertField')} <ChevronDown className="ml-2 h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {AVAILABLE_TOKENS.map((token) => (
          <DropdownMenuItem
            key={token.value}
            onClick={() => onInsertToken(`{{${token.value}}}`)}
            className="flex flex-col items-start py-2"
          >
            <span className="font-medium">{t(token.labelKey as any)}</span>
            <span className="text-xs text-muted-foreground">{t(token.descriptionKey as any)}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

