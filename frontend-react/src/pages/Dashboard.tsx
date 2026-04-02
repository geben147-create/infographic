import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, type RunSummary } from '@/lib/api'
import { formatCost, formatRelativeTime } from '@/lib/utils'
import { PageHeader } from '@/components/layout/PageHeader'
import { StatCard } from '@/components/ui/StatCard'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { HealthDot } from '@/components/ui/HealthDot'
import { EmptyState } from '@/components/ui/EmptyState'
import { CardSkeleton, TableSkeleton } from '@/components/ui/Skeleton'
import {
  Play,
  Loader,
  Upload,
  DollarSign,
  Plus,
} from 'lucide-react'

export default function Dashboard() {
  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ['dashboard-runs'],
    queryFn: () => api.getRuns({ limit: 5 }),
    refetchInterval: 30000,
  })

  const { data: costsData, isLoading: costsLoading } = useQuery({
    queryKey: ['dashboard-costs'],
    queryFn: () => api.getCosts({ days: 30 }),
    refetchInterval: 30000,
  })

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 30000,
  })

  const runs = runsData?.runs || []
  const totalRuns = runsData?.total || 0
  const runningCount = runs.filter((r: RunSummary) => r.status === 'running').length
  const readyCount = runs.filter((r: RunSummary) => r.status === 'ready_to_upload').length

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Pipeline overview and system health"
        action={
          <Link
            to="/trigger"
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Video
          </Link>
        }
      />

      {/* Stat Cards */}
      {runsLoading || costsLoading ? (
        <div className="grid grid-cols-4 gap-4 mb-6">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard
            label="Total Runs"
            value={totalRuns}
            icon={Play}
          />
          <StatCard
            label="Running Now"
            value={runningCount}
            icon={Loader}
            iconColor="text-blue-600 bg-blue-50"
          />
          <StatCard
            label="Ready to Upload"
            value={readyCount}
            icon={Upload}
            iconColor="text-emerald-600 bg-emerald-50"
          />
          <StatCard
            label="30-Day Cost"
            value={formatCost(costsData?.total_cost_usd)}
            icon={DollarSign}
            iconColor="text-amber-600 bg-amber-50"
          />
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Recent Runs */}
        <div className="col-span-2">
          {runsLoading ? (
            <TableSkeleton rows={5} />
          ) : runs.length === 0 ? (
            <div className="bg-surface rounded-xl border border-border">
              <EmptyState
                title="No pipelines yet"
                description="Create your first video to get started"
                actionLabel="Create Video"
                actionTo="/trigger"
              />
            </div>
          ) : (
            <div className="bg-surface rounded-xl border border-border">
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-border-light">
                <h2 className="text-sm font-semibold">Recent Pipelines</h2>
                <Link to="/pipelines" className="text-xs text-primary-500 hover:text-primary-600 font-medium">
                  View all
                </Link>
              </div>
              <div className="divide-y divide-border-light">
                {runs.map((run: RunSummary) => (
                  <Link
                    key={run.workflow_id}
                    to={`/pipelines/${run.workflow_id}`}
                    className="flex items-center gap-4 px-5 py-3 hover:bg-surface-hover transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-text-primary truncate font-mono">
                        {run.workflow_id}
                      </p>
                      <p className="text-xs text-text-secondary">{run.channel_id}</p>
                    </div>
                    <StatusBadge status={run.status} />
                    <span className="text-xs text-text-tertiary w-16 text-right">
                      {formatRelativeTime(run.started_at)}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right column: Cost + Health */}
        <div className="space-y-4">
          {/* Cost Breakdown */}
          {costsData && costsData.by_channel.length > 0 && (
            <div className="bg-surface rounded-xl border border-border p-5">
              <h2 className="text-sm font-semibold mb-3">Cost by Channel</h2>
              <div className="space-y-3">
                {costsData.by_channel.map((ch) => {
                  const pct = costsData.total_cost_usd > 0
                    ? (ch.total_cost_usd / costsData.total_cost_usd) * 100
                    : 0
                  return (
                    <div key={ch.channel_id}>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-text-secondary">{ch.channel_id}</span>
                        <span className="font-medium">{formatCost(ch.total_cost_usd)}</span>
                      </div>
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-primary-400 to-primary-600 rounded-full transition-all"
                          style={{ width: `${Math.max(pct, 2)}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* System Health */}
          {health && (
            <div className="space-y-2">
              <h2 className="text-sm font-semibold px-1">System Health</h2>
              <HealthDot ok={health.temporal} label="Temporal" detail={health.temporal ? 'Connected' : 'Disconnected'} />
              <HealthDot ok={health.sqlite} label="SQLite" detail={health.sqlite ? 'Healthy' : 'Error'} />
              <HealthDot ok={health.disk_free_gb > 5} label="Disk" detail={`${health.disk_free_gb} GB free`} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
