import React, { createContext, useContext, forwardRef } from 'react'
import { cn } from '@/utils/cn'
import { AlertCircle, CheckCircle, Info } from 'lucide-react'

// Form context for managing form state
const FormContext = createContext<any>(undefined)

interface FormProps extends React.FormHTMLAttributes<HTMLFormElement> {
  children: React.ReactNode
}

// Root form provider
function Form({ children, className, ...props }: FormProps) {
  return (
    <form className={cn('prelude-form', className)} {...props}>
      {children}
    </form>
  )
}

interface FormFieldProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

// Form field container
function FormField({ children, className }: FormFieldProps) {
  return <div className={cn('form-field space-y-1.5', className)}>{children}</div>
}

interface FormLabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {
  required?: boolean
  children: React.ReactNode
}

// Form label with proper accessibility
const FormLabel = forwardRef<HTMLLabelElement, FormLabelProps>(
  ({ className, required, children, ...props }, ref) => {
    return (
      <label
        ref={ref}
        className={cn('form-label text-sm font-medium text-ink', className)}
        {...props}
      >
        {children}
        {required && (
          <span className="ml-1 text-threat" aria-label="required">
            *
          </span>
        )}
      </label>
    )
  }
)
FormLabel.displayName = 'FormLabel'

interface FormInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean
  success?: boolean
}

// Form input with error states
const FormInput = forwardRef<HTMLInputElement, FormInputProps>(
  ({ className, error, success, disabled, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          // Base styles
          'flex h-10 w-full rounded-md border px-3 py-2 text-sm transition-colors duration-200',
          'file:border-0 file:bg-transparent file:text-sm file:font-medium',
          'placeholder:text-muted-foreground',
          'focus-visible:outline-none',
          'disabled:cursor-not-allowed disabled:opacity-50',

          // State-based styling
          error
            ? 'border-threat bg-threat-lo focus-visible:border-threat-hi'
            : success
              ? 'border-accent bg-accent-lo focus-visible:border-accent-hi'
              : 'border-rule bg-paper focus-visible:border-accent',

          className
        )}
        aria-invalid={!!error}
        disabled={disabled}
        {...props}
      />
    )
  }
)
FormInput.displayName = 'FormInput'

interface FormTextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean
  success?: boolean
}

// Form textarea with error states
const FormTextarea = forwardRef<HTMLTextAreaElement, FormTextareaProps>(
  ({ className, error, success, disabled, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          'flex min-h-[80px] w-full rounded-md border px-3 py-2 text-sm transition-colors duration-200',
          'resize-none placeholder:text-muted-foreground',
          'focus-visible:outline-none',
          'disabled:cursor-not-allowed disabled:opacity-50',

          error
            ? 'border-threat bg-threat-lo focus-visible:border-threat-hi'
            : success
              ? 'border-accent bg-accent-lo focus-visible:border-accent-hi'
              : 'border-rule bg-paper focus-visible:border-accent',

          className
        )}
        aria-invalid={!!error}
        disabled={disabled}
        {...props}
      />
    )
  }
)
FormTextarea.displayName = 'FormTextarea'

interface FormErrorProps extends React.HTMLAttributes<HTMLDivElement> {
  id?: string
  children: React.ReactNode | null | undefined
}

// Form error message with proper ARIA
function FormError({ id, children, className, ...props }: FormErrorProps) {
  if (!children) return null

  return (
    <div
      id={id}
      role="alert"
      aria-live="polite"
      className={cn(
        'flex items-center gap-1.5 text-sm text-threat',
        'animate-in duration-200 fade-in-0 slide-in-from-top-1',
        className
      )}
      {...props}
    >
      <AlertCircle className="h-4 w-4 flex-shrink-0" />
      <span>{children}</span>
    </div>
  )
}

interface FormSuccessProps extends React.HTMLAttributes<HTMLDivElement> {
  id?: string
  children: React.ReactNode | null | undefined
}

// Form success message
function FormSuccess({ id, children, className, ...props }: FormSuccessProps) {
  if (!children) return null

  return (
    <div
      id={id}
      className={cn(
        'flex items-center gap-1.5 text-sm text-accent',
        'animate-in duration-200 fade-in-0 slide-in-from-top-1',
        className
      )}
      {...props}
    >
      <CheckCircle className="h-4 w-4 flex-shrink-0" />
      <span>{children}</span>
    </div>
  )
}

interface FormHelpProps extends React.HTMLAttributes<HTMLDivElement> {
  id?: string
  children: React.ReactNode | null | undefined
}

// Form help text
function FormHelp({ id, children, className, ...props }: FormHelpProps) {
  if (!children) return null

  return (
    <div
      id={id}
      className={cn('flex items-center gap-1.5 text-xs text-muted-foreground', className)}
      {...props}
    >
      <Info className="h-3 w-3 flex-shrink-0" />
      <span>{children}</span>
    </div>
  )
}

interface FormFieldCompleteProps extends React.HTMLAttributes<HTMLDivElement> {
  label?: string
  name: string
  error?: string | null
  success?: string | null
  helpText?: string | null
  required?: boolean
  children: React.ReactNode
  [key: string]: any
}

// Complete form field component with all states
function FormFieldComplete({
  label,
  name,
  error,
  success,
  helpText,
  required = false,
  children,
  className,
  ...fieldProps
}: FormFieldCompleteProps) {
  const inputId = `${name}-input`
  const errorId = error ? `${name}-error` : undefined
  const helpId = helpText ? `${name}-help` : undefined
  const successId = success ? `${name}-success` : undefined

  const describedBy = [errorId, successId, helpId].filter(Boolean).join(' ') || undefined

  return (
    <FormField className={className}>
      {label && (
        <FormLabel htmlFor={inputId} required={required}>
          {label}
        </FormLabel>
      )}

      {/* Render children as-is, let parent handle ARIA attributes */}
      {React.Children.map(children, (child, index) => {
        // If it's a FormInput, clone with proper attributes
        if (React.isValidElement(child) && child.type === FormInput) {
          return React.cloneElement(child, {
            id: inputId,
            'aria-describedby': describedBy,
            error: !!error,
            success: !!success,
            name: name,
            ...fieldProps,
            ...(child.props as any),
          } as any)
        }
        // Otherwise render as-is
        return child
      })}

      <FormError id={errorId}>{error}</FormError>
      <FormSuccess id={successId}>{success}</FormSuccess>
      <FormHelp id={helpId}>{helpText}</FormHelp>
    </FormField>
  )
}

export {
  Form,
  FormField,
  FormLabel,
  FormInput,
  FormTextarea,
  FormError,
  FormSuccess,
  FormHelp,
  FormFieldComplete,
}
