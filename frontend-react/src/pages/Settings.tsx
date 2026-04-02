import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { PageHeader } from '@/components/layout/PageHeader'
import { HealthDot } from '@/components/ui/HealthDot'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { cn, formatRelativeTime } from '@/lib/utils'
import {
  ExternalLink,
  RefreshCw,
  Cpu,
  Server,
  HardDrive,
} from 'lucide-react'

export default function Settings() {
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 5000,
  })

  const { data: workers } = useQuery({
    queryKey: ['workers'],
    queryFn: api.getWorkers,
  })

  const { data: sysInfo } = useQuery({
    queryKey: ['system-info'],
    queryFn: api.getSystemInfo,
  })

  const { data: alerts } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api.getAlerts(20),
    refetchInterval: 30000,
  })

  const syncMutation = useMutation({
    mutationFn: api.triggerSync,
  })

  const workerIcons: Record<string, typeof Cpu> = {
    'GPU Worker': Cpu,
    'CPU Worker': Server,
    'API Worker': HardDrive,
  }

  return (
    <div>
      <PageHeader
        title="Settings"
        description="System health, workers, and configuration"
      />

      {/* Health Dashboard */}
      <div className="mb-6">
        <h2 className="text-sm font-semibold mb-3">System Health</h2>
        {healthLoading ? (
          <div className="grid grid-cols-3 gap-3">
            {Array.from({ length: 3 }).map((_, i) => <CardSkeleton key={i} />)}
          </div>
        ) : health ? (
          <div className="grid grid-cols-3 gap-3">
            <HealthDot ok={health.temporal} label="Temporal" detail={health.temporal ? 'Connected' : 'Disconnected'} />
            <HealthDot ok={health.sqlite} label="SQLite" detail={health.sqlite ? 'Healthy' : 'Error'} />
            <HealthDot ok={health.disk_free_gb > 5} label="Disk Space" detail={`${health.disk_free_gb} GB free`} />
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Workers */}
        <div>
          <h2 className="text-sm font-semibold mb-3">Worker Pools</h2>
          <div className="space-y-3">
            {workers?.workers.map((w) => {
              const Icon = workerIcons[w.name] || Server
              return (
                <div key={w.name} className="bg-surface rounded-xl border border-border p-4">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-lg bg-primary-50 flex items-center justify-center">
                      <Icon className="w-4.5 h-4.5 text-primary-500" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-semibold">{w.name}</h3>
                        <span className="text-xs font-mono bg-surface-secondary px-2 py-0.5 rounded">
                          max={w.max_concurrent}
                        </span>
                      </div>
                      <p className="text-xs text-text-secondary mt-0.5">{w.description}</p>
                      <p className="text-xs text-text-tertiary mt-1">Queue: {w.task_queue}</p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Services + Links */}
        <div className="space-y-6">
          {/* System Services */}
          <div>
            <h2 className="text-sm font-semibold mb-3">Services</h2>
            <div className="space-y-2">
              {sysInfo?.services.map((svc) => (
                <div key={svc.name} className="bg-surface rounded-xl border border-border p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <span className={cn(
                        'w-2.5 h-2.5 rounded-full',
                        svc.status === 'available' ? 'bg-success' : 'bg-danger'
                      )} />
                      <span className="text-sm font-medium">{svc.name}</span>
                    </div>
                    <span className="text-xs text-text-secondary font-mono">
                      {svc.version || svc.status}
                    </span>
                  </div>
                  {svc.url && (
                    <p className="text-xs text-text-tertiary mt-1 ml-5">{svc.url}</p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <h2 className="text-sm font-semibold mb-3">Quick Links</h2>
            <div className="space-y-2">
              <a
                href="http://localhost:8081"
                target="_blank"
                rel="noopener"
                className="flex items-center justify-between bg-surface rounded-xl border border-border p-4 hover:bg-surface-hover transition-colors"
              >
                <span className="text-sm font-medium">Temporal UI</span>
                <ExternalLink className="w-4 h-4 text-text-tertiary" />
              </a>
            </div>
          </div>

          {/* Sheets Sync */}
          <div>
            <h2 className="text-sm font-semibold mb-3">Google Sheets Sync</h2>
            <div className="bg-surface rounded-xl border border-border p-4">
              <button
                onClick={() => syncMutation.mutate()}
                disabled={syncMutation.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50"
              >
                <RefreshCw className={cn('w-4 h-4', syncMutation.isPending && 'animate-spin')} />
                {syncMutation.isPending ? 'Syncing...' : 'Sync Now'}
              </button>
              {syncMutation.isSuccess && (
                <p className="mt-2 text-xs text-success">
                  Sync started: {syncMutation.data?.workflow_id}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Alert Log */}
      {alerts && alerts.alerts.length > 0 && (
        <div className="mt-6">
          <h2 className="text-sm font-semibold mb-3">Recent Alerts</h2>
          <div className="bg-surface rounded-xl border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-secondary text-left">
                  <th className="px-5 py-2.5 text-xs font-semibold text-text-secondary uppercase">Time</th>
                  <th className="px-5 py-2.5 text-xs font-semibold text-text-secondary uppercase">Level</th>
                  <th className="px-5 py-2.5 text-xs font-semibold text-text-secondary uppercase">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light">
                {alerts.alerts.map((alert, i) => (
                  <tr key={i}>
                    <td className="px-5 py-2.5 text-xs text-text-tertiary">
                      {formatRelativeTime(alert.ts)}
                    </td>
                    <td className="px-5 py-2.5">
                      <span className={cn(
                        'text-xs px-2 py-0.5 rounded-full font-medium',
                        alert.level === 'critical' ? 'bg-red-100 text-red-700' :
                        alert.level === 'warning' ? 'bg-amber-100 text-amber-700' :
                        'bg-blue-100 text-blue-700'
                      )}>
                        {alert.level}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-text-secondary">{alert.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
