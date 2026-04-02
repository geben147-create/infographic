import { cn } from '@/lib/utils'

interface HealthDotProps {
  ok: boolean
  label: string
  detail?: string
}

export function HealthDot({ ok, label, detail }: HealthDotProps) {
  return (
    <div className="bg-surface rounded-xl border border-border p-4">
      <div className="flex items-center gap-2.5 mb-1">
        <span
          className={cn(
            'w-2.5 h-2.5 rounded-full',
            ok ? 'bg-success' : 'bg-danger'
          )}
        />
        <span className="text-sm font-medium text-text-primary">{label}</span>
      </div>
      {detail && (
        <p className="text-xs text-text-secondary ml-5">{detail}</p>
      )}
    </div>
  )
}
