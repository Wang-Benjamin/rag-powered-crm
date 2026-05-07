export interface Personnel {
  id?: string | number
  fullName?: string
  name?: string
  firstName?: string
  lastName?: string
  position?: string
  title?: string
  email?: string
  phone?: string
  linkedinUrl?: string
  department?: string
}

export interface PersonnelData {
  leadId: string | number
  personnel: Personnel[]
}
