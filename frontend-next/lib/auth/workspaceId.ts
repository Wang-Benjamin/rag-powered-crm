export function toWorkspaceId(userEmail: string | null | undefined): string {
  return userEmail ? btoa(userEmail).replace(/=/g, '') : 'default'
}
