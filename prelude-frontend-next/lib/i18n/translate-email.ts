/**
 * Translate email content to Chinese via backend proxy.
 * Strips the HTML signature before translating (signature stays in English),
 * then re-appends it to the translated body.
 */

import { crmApiClient } from '@/lib/api/client'

/** Strip dangerous HTML (scripts, event handlers) while keeping layout tags */
function sanitizeHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/\bon\w+\s*=\s*"[^"]*"/gi, '')
    .replace(/\bon\w+\s*=\s*'[^']*'/gi, '')
}

// Strip signature so it stays in original language (name, title, phone should not be translated)
const SIGNATURE_REGEX = /(\n*此致[,，]?\s*\n*)?(<div\s+style="font-size:\s*\d+px[\s\S]*$)/i

function splitSignature(body: string): { content: string; signature: string } {
  const match = body.match(SIGNATURE_REGEX)
  if (match) {
    return {
      content: body.slice(0, match.index!).trimEnd(),
      signature: match[0],
    }
  }
  return { content: body, signature: '' }
}

export async function translateEmailContent(
  subject: string,
  body: string
): Promise<{ subjectZh: string; bodyZh: string }> {
  const { content, signature } = splitSignature(body)

  const response = await crmApiClient.post<{
    subjectZh: string
    bodyZh: string
  }>('/translate', { subject, body: content })

  const bodyZh = signature ? `${response.bodyZh}\n\n${signature}` : response.bodyZh
  return {
    subjectZh: response.subjectZh,
    bodyZh: sanitizeHtml(bodyZh),
  }
}
