import { cn } from '@/lib/utils'
import { type LucideIcon } from 'lucide-react'

interface StatCardProps {
  label: string
  value: string | number
  icon: LucideIcon
  iconColor?: string
  trend?: string
  className?: string
}

export function StatCard({
  label,
  value,
  icon: Icon,
  iconColor = 'text-primary-500 bg-primary-50',
  trend,
  className,
}: StatCardProps) {
  return (
    <div
      className={cn(
        'bg-surface rounded-xl border border-border p-5 hover:shadow-sm transition-shadow',
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-text-secondary font-medium">{label}</p>
          <p className="mt-1.5 text-2xl font-semibold tracking-tight">{value}</p>
          {trend && (
            <p className="mt-1 text-xs text-text-tertiary">{trend}</p>
          )}
        </div>
        <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', iconColor)}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  )
}
