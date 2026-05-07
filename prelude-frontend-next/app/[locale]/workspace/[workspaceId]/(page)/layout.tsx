export default function PageLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-full overflow-hidden">
      <main className="h-full overflow-y-auto overflow-x-hidden p-3 pb-8">{children}</main>
    </div>
  )
}
