/**
 * Email Signature Type Definitions
 * Wire shape is camelCase via ApiClient case transform.
 */

export interface SignatureFields {
  name?: string
  title?: string
  email?: string
  phoneNumber?: string
  location?: string
  link?: string
  logoUrl?: string
}

export interface EmailSignature {
  signatureFields: SignatureFields
  updatedAt: string
}

export interface EmailTrainingSamples {
  subject1: string
  body1: string
  subject2: string
  body2: string
  subject3: string
  body3: string
}
