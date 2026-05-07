'use client'

import { ImageIcon } from 'lucide-react'
import { useState } from 'react'

interface ProductMediaProps {
  imageUrl?: string | null
  alt?: string
}

export function ProductMedia({ imageUrl, alt }: ProductMediaProps) {
  const [errored, setErrored] = useState(false)
  const showImage = Boolean(imageUrl) && !errored

  return (
    <div className="pc-media relative aspect-[4/3] w-full overflow-hidden border-b border-rule bg-cream">
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={imageUrl ?? ''}
          alt={alt ?? ''}
          loading="lazy"
          className="h-full w-full object-cover"
          onError={() => setErrored(true)}
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-mute">
          <ImageIcon className="h-10 w-10" strokeWidth={1.25} />
        </div>
      )}
    </div>
  )
}
