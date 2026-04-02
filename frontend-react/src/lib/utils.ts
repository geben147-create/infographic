import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCost(usd: number | null | undefined): string {
  if (usd === null || usd === undefined) return '--'
  return `$${usd.toFixed(2)}`
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '--'
  const date = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  const diffHr = Math.floor(diffMs / 3600000)
  const diffDay = Math.floor(diffMs / 86400000)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHr < 24) return `${diffHr}h ago`
  if (diffDay < 7) return `${diffDay}d ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function statusColor(status: string): string {
  const colors: Record<string, string> = {
    running: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    ready_to_upload: 'bg-emerald-100 text-emerald-700',
    waiting_approval: 'bg-amber-100 text-amber-700',
    failed: 'bg-red-100 text-red-700',
    unknown: 'bg-gray-100 text-gray-500',
    pending: 'bg-gray-100 text-gray-500',
  }
  return colors[status] || colors.unknown
}

export function statusDotColor(status: string): string {
  const colors: Record<string, string> = {
    running: 'bg-blue-500',
    completed: 'bg-green-500',
    ready_to_upload: 'bg-emerald-500',
    waiting_approval: 'bg-amber-500',
    failed: 'bg-red-500',
    unknown: 'bg-gray-400',
    pending: 'bg-gray-400',
  }
  return colors[status] || colors.unknown
}
