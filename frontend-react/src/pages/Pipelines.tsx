import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, type RunSummary } from '@/lib/api'
import { formatCost, formatRelativeTime } from '@/lib/utils'
import { PageHeader } from '@/components/layout/PageHeader'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { EmptyState } from '@/components/ui/EmptyState'
import { TableSkeleton } from '@/components/ui/Skeleton'
import { Plus, Download, ChevronLeft, ChevronRight } from 'lucide-react'

const PAGE_SIZE = 20

const STATUS_OPTIONS = [
  { value: '', label: 'All Status' },
  { value: 'running', label: 'Running' },
  { value: 'completed', label: 'Completed' },
  { value: 'ready_to_upload', label: 'Ready' },
  { value: 'waiting_approval', label: 'Awaiting' },
  { value: 'failed', label: 'Failed' },
]

export default function Pipelines() {
  const [offset, setOffset] = useState(0)
  const [channelFilter, setChannelFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const { data: channelsData } = useQuery({
    queryKey: ['channels'],
    queryFn: api.getChannels,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['runs', offset, channelFilter, statusFilter],
    queryFn: () =>
      api.getRuns({
        limit: PAGE_SIZE,
        offset,
        channel_id: channelFilter || undefined,
        status: statusFilter || undefined,
      }),
    refetchInterval: 15000,
  })

  const runs = data?.runs || []
  const total = data?.total || 0

  return (
    <div>
      <PageHeader
        title="Pipeline Runs"
        description={`${total} total runs`}
        action={
          <Link
            to="/trigger"
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Pipeline
          </Link>
        }
      />

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={channelFilter}
          onChange={(e) => { setChannelFilter(e.target.value); setOffset(0) }}
          className="px-3 py-2 text-sm border border-border rounded-lg bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-primary-200"
        >
          <option value="">All Channels</option>
          {channelsData?.channels.map((ch) => (
            <option key={ch.channel_id} value={ch.channel_id}>
              {ch.channel_id}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 text-sm border border-border rounded-lg bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-primary-200"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      {isLoading ? (
        <TableSkeleton rows={8} />
      ) : runs.length === 0 ? (
        <div className="bg-surface rounded-xl border border-border">
          <EmptyState
            title="No pipelines found"
            description="Start your first video pipeline"
            actionLabel="Create Video"
            actionTo="/trigger"
          />
        </div>
      ) : (
        <div className="bg-surface rounded-xl border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-secondary text-left">
                <th className="px-5 py-3 text-xs font-semibold text-text-secondary uppercase tracking-wider">Workflow</th>
                <th className="px-5 py-3 text-xs font-semibold text-text-secondary uppercase tracking-wider">Channel</th>
                <th className="px-5 py-3 text-xs font-semibold text-text-secondary uppercase tracking-wider">Status</th>
                <th className="px-5 py-3 text-xs font-semibold text-text-secondary uppercase tracking-wider text-right">Cost</th>
                <th className="px-5 py-3 text-xs font-semibold text-text-secondary uppercase tracking-wider text-right">Started</th>
                <th className="px-5 py-3 text-xs font-semibold text-text-secondary uppercase tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-light">
              {runs.map((run: RunSummary) => (
                <tr
                  key={run.workflow_id}
                  className={`hover:bg-surface-hover transition-colors ${
                    run.status === 'failed' ? 'border-l-3 border-l-danger' : ''
                  }`}
                >
                  <td className="px-5 py-3">
                    <Link
                      to={`/pipelines/${run.workflow_id}`}
                      className="text-sm font-medium text-primary-500 hover:text-primary-600 font-mono"
                    >
                      {run.workflow_id.slice(0, 20)}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-text-secondary">{run.channel_id}</td>
                  <td className="px-5 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-5 py-3 text-right text-text-secondary font-mono">
                    {formatCost(run.total_cost_usd)}
                  </td>
                  <td className="px-5 py-3 text-right text-text-tertiary text-xs">
                    {formatRelativeTime(run.started_at)}
                  </td>
                  <td className="px-5 py-3 text-right">
                    {(run.status === 'ready_to_upload' || run.status === 'completed') && run.video_path && (
                      <a
                        href={`/api/pipeline/${run.workflow_id}/download`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-primary-500 hover:bg-primary-50 rounded-md transition-colors"
                      >
                        <Download className="w-3.5 h-3.5" />
                        Video
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          <div className="flex items-center justify-between px-5 py-3 border-t border-border-light bg-surface-secondary">
            <span className="text-xs text-text-secondary">
              {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </span>
            <div className="flex gap-1">
              <button
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0}
                className="p-1.5 rounded-md hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= total}
                className="p-1.5 rounded-md hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
