'use client'

import { useMemo } from 'react'
import DOMPurify from 'isomorphic-dompurify'

interface SafeHtmlProps extends React.HTMLAttributes<HTMLDivElement> {
  html: string
}

export function SafeHtml({ html, ...props }: SafeHtmlProps) {
  const clean = useMemo(
    () =>
      DOMPurify.sanitize(html, {
        ALLOWED_TAGS: [
          'b',
          'i',
          'em',
          'strong',
          'a',
          'p',
          'br',
          'ul',
          'ol',
          'li',
          'h1',
          'h2',
          'h3',
          'h4',
          'h5',
          'h6',
          'span',
          'div',
          'img',
          'table',
          'thead',
          'tbody',
          'tr',
          'td',
          'th',
          'blockquote',
          'pre',
          'code',
        ],
        ALLOWED_ATTR: [
          'href',
          'target',
          'rel',
          'src',
          'alt',
          'class',
          'style',
          'width',
          'height',
          'colspan',
          'rowspan',
        ],
      }),
    [html]
  )

  return <div {...props} dangerouslySetInnerHTML={{ __html: clean }} />
}
