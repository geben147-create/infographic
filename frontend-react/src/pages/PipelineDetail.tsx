import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { formatCost, formatRelativeTime, cn } from '@/lib/utils'
import { PageHeader } from '@/components/layout/PageHeader'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import {
  ArrowLeft,
  Download,
  ThumbsUp,
  ThumbsDown,
  XCircle,
  Check,
  Loader,
  Circle,
} from 'lucide-react'

const PIPELINE_STEPS = [
  'Setup Dirs',
  'Script Gen',
  'Image Gen',
  'TTS',
  'Video Gen',
  'Thumbnail',
  'Assembly',
  'Quality Gate',
]

function StepProgress({ currentStep }: { currentStep?: string | null }) {
  // Rough mapping of step names to index
  const stepIndex = currentStep
    ? PIPELINE_STEPS.findIndex((s) =>
        currentStep.toLowerCase().includes(s.toLowerCase().split(' ')[0].toLowerCase())
      )
    : -1

  return (
    <div className="flex items-center gap-1">
      {PIPELINE_STEPS.map((step, i) => {
        const isDone = stepIndex > i
        const isCurrent = stepIndex === i
        const isPending = stepIndex < i

        return (
          <div key={step} className="flex items-center gap-1">
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'w-7 h-7 rounded-full flex items-center justify-center text-xs',
                  isDone && 'bg-green-500 text-white',
                  isCurrent && 'bg-blue-500 text-white',
                  isPending && 'bg-gray-100 text-gray-400',
                  !isDone && !isCurrent && !isPending && 'bg-gray-100 text-gray-400'
                )}
              >
                {isDone ? (
                  <Check className="w-3.5 h-3.5" />
                ) : isCurrent ? (
                  <Loader className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Circle className="w-3 h-3" />
                )}
              </div>
              <span className="text-[10px] text-text-tertiary mt-1 w-14 text-center leading-tight">
                {step}
              </span>
            </div>
            {i < PIPELINE_STEPS.length - 1 && (
              <div
                className={cn(
                  'w-6 h-0.5 mb-4',
                  isDone ? 'bg-green-400' : 'bg-gray-200'
                )}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function PipelineDetail() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const { data: status, isLoading } = useQuery({
    queryKey: ['pipeline-status', id],
    queryFn: () => api.getPipelineStatus(id!),
    refetchInterval: (query) =>
      query.state.data?.status === 'running' ? 3000 : 30000,
    enabled: !!id,
  })

  const { data: costData } = useQuery({
    queryKey: ['pipeline-cost', id],
    queryFn: () => api.getPipelineCost(id!),
    enabled: !!id,
  })

  const approveMutation = useMutation({
    mutationFn: (approved: boolean) => api.approvePipeline(id!, approved),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline-status', id] }),
  })

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelPipeline(id!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline-status', id] }),
  })

  if (isLoading) {
    return (
      <div>
        <PageHeader title="Pipeline Detail" />
        <div className="grid grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      </div>
    )
  }

  if (!status) return null

  const isReady = status.status === 'ready_to_upload' || status.status === 'completed'
  const isWaiting = status.status === 'waiting_approval'
  const isRunning = status.status === 'running'

  return (
    <div>
      <Link to="/pipelines" className="inline-flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary mb-4">
        <ArrowLeft className="w-4 h-4" />
        Back to Pipelines
      </Link>

      <PageHeader
        title={id || ''}
        action={<StatusBadge status={status.status} />}
      />

      {/* Step Progress */}
      {isRunning && (
        <div className="bg-surface rounded-xl border border-border p-5 mb-6">
          <h3 className="text-sm font-semibold mb-4">Pipeline Progress</h3>
          <StepProgress currentStep={status.current_step} />
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Main content */}
        <div className="col-span-2 space-y-4">
          {/* Video Preview */}
          {isReady && (
            <div className="bg-surface rounded-xl border border-border p-5">
              <h3 className="text-sm font-semibold mb-3">Video Preview</h3>
              <video
                controls
                className="w-full rounded-lg bg-black"
                src={`/api/pipeline/${id}/video`}
              />
              <div className="flex gap-3 mt-4">
                <a
                  href={`/api/pipeline/${id}/download`}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600"
                >
                  <Download className="w-4 h-4" />
                  Download Video
                </a>
                <a
                  href={`/api/pipeline/${id}/thumbnail`}
                  className="inline-flex items-center gap-2 px-4 py-2 border border-border text-sm font-medium rounded-lg hover:bg-surface-hover"
                >
                  <Download className="w-4 h-4" />
                  Download Thumbnail
                </a>
              </div>
            </div>
          )}

          {/* Approval actions */}
          {isWaiting && (
            <div className="bg-amber-50 rounded-xl border border-amber-200 p-5">
              <h3 className="text-sm font-semibold text-amber-800 mb-3">
                Waiting for Approval
              </h3>
              <div className="flex gap-3">
                <button
                  onClick={() => approveMutation.mutate(true)}
                  disabled={approveMutation.isPending}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-green-500 text-white text-sm font-medium rounded-lg hover:bg-green-600 disabled:opacity-50"
                >
                  <ThumbsUp className="w-4 h-4" />
                  Approve
                </button>
                <button
                  onClick={() => approveMutation.mutate(false)}
                  disabled={approveMutation.isPending}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-red-500 text-white text-sm font-medium rounded-lg hover:bg-red-600 disabled:opacity-50"
                >
                  <ThumbsDown className="w-4 h-4" />
                  Reject
                </button>
              </div>
            </div>
          )}

          {/* Error panel */}
          {status.status === 'failed' && status.error && (
            <div className="bg-red-50 rounded-xl border border-red-200 p-5">
              <h3 className="text-sm font-semibold text-red-800 mb-2">Error</h3>
              <pre className="text-xs text-red-700 bg-red-100 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
                {status.error}
              </pre>
            </div>
          )}

          {/* Cost Breakdown */}
          {costData && costData.breakdown.length > 0 && (
            <div className="bg-surface rounded-xl border border-border p-5">
              <h3 className="text-sm font-semibold mb-3">Cost Breakdown</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-text-secondary">
                    <th className="pb-2">Service</th>
                    <th className="pb-2">Step</th>
                    <th className="pb-2 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-light">
                  {costData.breakdown.map((item, i) => (
                    <tr key={i}>
                      <td className="py-2 text-text-secondary">{item.service}</td>
                      <td className="py-2 font-mono text-xs">{item.step}</td>
                      <td className="py-2 text-right font-mono">{formatCost(item.amount_usd)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-border">
                    <td colSpan={2} className="pt-2 font-semibold">Total</td>
                    <td className="pt-2 text-right font-semibold font-mono">
                      {formatCost(costData.total_cost_usd)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>

        {/* Right sidebar */}
        <div className="space-y-4">
          {/* Metadata */}
          <div className="bg-surface rounded-xl border border-border p-5">
            <h3 className="text-sm font-semibold mb-3">Details</h3>
            <dl className="space-y-2.5 text-sm">
              <div>
                <dt className="text-text-tertiary text-xs">Status</dt>
                <dd><StatusBadge status={status.status} /></dd>
              </div>
              <div>
                <dt className="text-text-tertiary text-xs">Started</dt>
                <dd className="text-text-secondary">{formatRelativeTime(status.started_at)}</dd>
              </div>
              {status.completed_at && (
                <div>
                  <dt className="text-text-tertiary text-xs">Completed</dt>
                  <dd className="text-text-secondary">{formatRelativeTime(status.completed_at)}</dd>
                </div>
              )}
              <div>
                <dt className="text-text-tertiary text-xs">Cost</dt>
                <dd className="font-mono">{formatCost(status.cost_so_far_usd)}</dd>
              </div>
              {status.youtube_url && (
                <div>
                  <dt className="text-text-tertiary text-xs">YouTube</dt>
                  <dd>
                    <a href={status.youtube_url} target="_blank" rel="noopener" className="text-primary-500 hover:underline text-xs">
                      View on YouTube
                    </a>
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Cancel button */}
          {isRunning && (
            <button
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 border border-red-200 text-red-600 text-sm font-medium rounded-lg hover:bg-red-50 disabled:opacity-50"
            >
              <XCircle className="w-4 h-4" />
              Cancel Pipeline
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
