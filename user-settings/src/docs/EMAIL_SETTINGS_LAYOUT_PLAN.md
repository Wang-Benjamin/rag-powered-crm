# Email Settings Layout Redesign Plan

## Current State

The existing Email Settings page uses a **horizontal two-column layout** with Email Personality Training on the left and Email Signature (with logo, sliders, preview) on the right.

## Target Layout (from Cosailor Reference)

The reference uses a **simple vertical card-based layout**:

```
Container (w-full h-full p-8 space-y-8 bg-muted/30)
│
├── Page Header
│   ├── Title (text-2xl font-semibold)
│   └── Description (text-muted-foreground text-sm)
│
├── Card 1
│   ├── CardHeader (border-b border-border pb-4)
│   │   └── CardTitle (text-lg font-medium)
│   └── CardContent (p-6 space-y-6)
│       └── Content...
│
└── Card 2
    ├── CardHeader (border-b border-border pb-4)
    │   └── CardTitle (text-lg font-medium)
    └── CardContent (p-6 space-y-6)
        └── Content...
```

---

## Proposed Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  p-8 space-y-8 bg-muted/30                                              │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Email Settings                                    (text-2xl)       │  │
│  │ Configure your email personality and signature    (text-sm muted)  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Card: Email Personality Training                                   │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │ CardHeader (border-b pb-4)                                         │  │
│  │ "Email Personality Training"                                       │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │ CardContent (p-6 space-y-6)                                        │  │
│  │                                                                    │  │
│  │  Status: [Trained - 3 samples]  Your AI uses your tone  [Update]  │  │
│  │                                                                    │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │ #1  Room rental inquiry — 100 La Salle St...             ⚙  │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │ #2  Room rental inquiry — 100 La Salle St...             ⚙  │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │ #3  Room rental inquiry — 100 La Salle St...             ⚙  │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │                                                                    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Card: Email Signature                                              │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │ CardHeader (border-b pb-4)                                         │  │
│  │ "Email Signature"                                                  │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │ CardContent (p-6 space-y-6)                                        │  │
│  │                                                                    │  │
│  │  Your Email Signature (Label)                                      │  │
│  │                                                                    │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │ RichTextEditor                                              │  │  │
│  │  │ ┌─────────────────────────────────────────────────────────┐ │  │  │
│  │  │ │ [B] [I] [U] | [◀] [▬] [▶] | [🔗]      (toolbar)         │ │  │  │
│  │  │ └─────────────────────────────────────────────────────────┘ │  │  │
│  │  │ ┌─────────────────────────────────────────────────────────┐ │  │  │
│  │  │ │                                                         │ │  │  │
│  │  │ │ James Smith                                             │ │  │  │
│  │  │ │ Prelude Technologies                                    │ │  │  │
│  │  │ │ Phone: (555) 123-4567                                   │ │  │  │
│  │  │ │ https://preludeos.com/                                  │ │  │  │
│  │  │ │                                          (min-h: 200px) │ │  │  │
│  │  │ └─────────────────────────────────────────────────────────┘ │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │                                                                    │  │
│  │  ┌──────────────────────────┐                                      │  │
│  │  │ 💾 Save Email Signature  │  (w-full sm:w-auto)                  │  │
│  │  └──────────────────────────┘                                      │  │
│  │                                                                    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Structure

```
EmailSettingsPage
├── Container (div: w-full h-full p-8 space-y-8 bg-muted/30)
│
├── Header (div: mb-8)
│   ├── h1: "Email Settings" (text-2xl font-semibold text-foreground mb-2)
│   └── p: description (text-muted-foreground text-sm)
│
├── Card: Email Personality Training (border-border shadow-sm)
│   ├── CardHeader (border-b border-border pb-4)
│   │   └── CardTitle: "Email Personality Training" (text-lg font-medium)
│   └── CardContent (p-6 space-y-6)
│       ├── Status row (flex items-center justify-between)
│       │   ├── Badge + description text
│       │   └── Update button
│       └── Samples list (space-y-3)
│           └── Sample items (border rounded-lg p-4 hover:bg-muted/50)
│
└── Card: Email Signature (border-border shadow-sm)
    ├── CardHeader (border-b border-border pb-4)
    │   └── CardTitle: "Email Signature" (text-lg font-medium)
    └── CardContent (p-6 space-y-6)
        ├── div (space-y-4)
        │   ├── Label: "Your Email Signature"
        │   └── RichTextEditor (minHeight={200})
        └── Button: "Save Email Signature" (w-full sm:w-auto)
```

---

## Reference Code Pattern

From `/Users/james/Desktop/instalily-sales-cosailor/apps/nextjs/src/components/settings/SettingsPageClient.tsx`:

### Container
```tsx
<div className="w-full h-full p-8 space-y-8 bg-muted/30">
```

### Page Header
```tsx
<div className="mb-8">
  <h1 className="text-2xl font-semibold text-foreground mb-2">Email Settings</h1>
  <p className="text-muted-foreground text-sm">
    Configure your email personality and signature
  </p>
</div>
```

### Card Pattern
```tsx
<Card className="border-border shadow-sm">
  <CardHeader className="border-b border-border pb-4">
    <CardTitle className="text-lg font-medium text-foreground">
      Email Signature
    </CardTitle>
  </CardHeader>
  <CardContent className="p-6 space-y-6">
    {/* Content */}
  </CardContent>
</Card>
```

### Email Signature Section (Exact Pattern)
```tsx
<Card className="border-border shadow-sm">
  <CardHeader className="border-b border-border pb-4">
    <CardTitle className="text-lg font-medium text-foreground">
      Email Signature
    </CardTitle>
  </CardHeader>
  <CardContent className="p-6 space-y-6">
    <div className="space-y-4">
      <Label className="text-sm font-medium">
        Your Email Signature
      </Label>

      <RichTextEditor
        value={emailSignatureRich}
        onChange={(text, html) => {
          setEmailSignaturePlain(text);
          setEmailSignatureRich(html);
        }}
        placeholder={`Create your professional email signature...`}
        minHeight={200}
        className="w-full"
      />
    </div>
    <Button
      onClick={handleSaveSignature}
      disabled={isLoading}
      className="w-full sm:w-auto"
      size="lg"
    >
      <Save className="h-4 w-4 mr-2" />
      {isLoading ? "Saving..." : "Save Email Signature"}
    </Button>
  </CardContent>
</Card>
```

### Email Personality Training Section (New)
```tsx
<Card className="border-border shadow-sm">
  <CardHeader className="border-b border-border pb-4">
    <CardTitle className="text-lg font-medium text-foreground">
      Email Personality Training
    </CardTitle>
  </CardHeader>
  <CardContent className="p-6 space-y-6">
    {/* Status Row */}
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <Badge className="bg-green-100 text-green-700">
          Trained - 3 samples
        </Badge>
        <span className="text-sm text-muted-foreground">
          Your AI uses your tone
        </span>
      </div>
      <Button variant="outline" size="sm">
        Update
      </Button>
    </div>

    {/* Samples List */}
    <div className="space-y-3">
      {samples.map((sample, index) => (
        <div
          key={index}
          className="border border-border rounded-lg p-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
        >
          <div className="space-y-1">
            <p className="text-sm font-medium">#{index + 1}</p>
            <p className="text-xs text-muted-foreground">
              {sample.subject}
            </p>
          </div>
          <Button variant="ghost" size="icon">
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      ))}
    </div>
  </CardContent>
</Card>
```

---

## Key Differences from Current

| Aspect | Current | New |
|--------|---------|-----|
| Layout | Two-column horizontal | Single-column vertical |
| Background | None | `bg-muted/30` |
| Spacing | Mixed | `space-y-8` between cards |
| Card style | Basic | `border-border shadow-sm` |
| Card header | Simple | `border-b border-border pb-4` |
| Card content | Basic | `p-6 space-y-6` |
| Signature editor | Plain textarea + logo + sliders | RichTextEditor only |

---

## Implementation Checklist

1. [ ] Create container with `w-full h-full p-8 space-y-8 bg-muted/30`
2. [ ] Add page header with title and description
3. [ ] Create Email Personality Training Card
   - [ ] CardHeader with border-b
   - [ ] Status row with badge and Update button
   - [ ] Sample items list with hover states
4. [ ] Create Email Signature Card
   - [ ] CardHeader with border-b
   - [ ] Label for signature
   - [ ] RichTextEditor component (minHeight 200)
   - [ ] Save button (w-full sm:w-auto)
5. [ ] Remove old logo upload, sliders, and preview sections
6. [ ] Use zinc color palette only (per CLAUDE.md)
7. [ ] Add loading states for save operations

---

## Notes

- The reference does NOT use nested cards for subsections
- The RichTextEditor handles formatting internally (toolbar is part of the component)
- No separate preview section needed - the editor IS the preview
- Keep it simple: Label → Editor → Save Button
