import { cn, statusColor, statusDotColor } from '@/lib/utils'

interface StatusBadgeProps {
  status: string
  className?: string
}

const labelMap: Record<string, string> = {
  running: 'Running',
  completed: 'Completed',
  ready_to_upload: 'Ready',
  waiting_approval: 'Awaiting',
  failed: 'Failed',
  unknown: 'Unknown',
  pending: 'Pending',
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium',
        statusColor(status),
        className
      )}
    >
      <span
        className={cn(
          'w-1.5 h-1.5 rounded-full',
          statusDotColor(status),
          status === 'running' && 'animate-pulse'
        )}
      />
      {labelMap[status] || status}
    </span>
  )
}
