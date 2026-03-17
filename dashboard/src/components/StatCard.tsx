interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  valueColor?: string
}

export function StatCard({ title, value, subtitle, valueColor }: StatCardProps) {
  return (
    <div className="bg-card border border-border rounded-lg p-5 flex flex-col gap-1">
      <span className="text-xs font-medium text-muted uppercase tracking-wider">{title}</span>
      <span
        className={`text-3xl font-bold tabular-nums ${valueColor ?? 'text-white'}`}
      >
        {value}
      </span>
      {subtitle && <span className="text-xs text-muted">{subtitle}</span>}
    </div>
  )
}
