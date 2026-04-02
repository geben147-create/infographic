import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, type ChannelWithStats } from '@/lib/api'
import { cn, formatCost } from '@/lib/utils'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { Radio, Sparkles } from 'lucide-react'

function ModelBadge({ label, value, isLocal }: { label: string; value: string; isLocal: boolean }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-text-tertiary">{label}</span>
      <span className={cn(
        'px-1.5 py-0.5 rounded font-medium',
        isLocal ? 'bg-green-50 text-green-600' : 'bg-blue-50 text-blue-600'
      )}>
        {value.replace('local:', '').replace('fal:', '').replace('together:', '')}
      </span>
    </div>
  )
}

function ChannelCard({ channel }: { channel: ChannelWithStats }) {
  const isLocal = (model: string) => model.startsWith('local:')

  return (
    <div className="bg-surface rounded-xl border border-border p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-base font-semibold">{channel.channel_id}</h3>
          <p className="text-xs text-text-secondary mt-0.5">
            {channel.niche} / {channel.language.toUpperCase()}
          </p>
        </div>
        <div className="flex gap-1.5">
          {channel.vgen_enabled && (
            <span className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded font-medium">
              Cloud Video
            </span>
          )}
          {channel.quality_gate_enabled && (
            <span className="text-[10px] px-1.5 py-0.5 bg-amber-50 text-amber-600 rounded font-medium">
              Quality Gate
            </span>
          )}
        </div>
      </div>

      {/* Model badges */}
      <div className="space-y-1.5 mb-4">
        <ModelBadge label="LLM" value={channel.llm_model} isLocal={isLocal(channel.llm_model)} />
        <ModelBadge label="Image" value={channel.image_model} isLocal={isLocal(channel.image_model)} />
        <ModelBadge label="TTS" value={channel.tts_model} isLocal={isLocal(channel.tts_model)} />
        <ModelBadge label="Video" value={channel.video_model} isLocal={isLocal(channel.video_model)} />
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-text-secondary pt-3 border-t border-border-light">
        <span>Runs: <strong className="text-text-primary">{channel.total_runs}</strong></span>
        <span>Success: <strong className="text-text-primary">{channel.success_rate}%</strong></span>
        <span>Avg: <strong className="text-text-primary font-mono">{formatCost(channel.avg_cost_usd)}</strong></span>
      </div>

      {/* Actions */}
      <div className="flex gap-2 mt-4">
        <Link
          to={`/trigger?channel=${channel.channel_id}`}
          className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-primary-500 text-white text-xs font-medium rounded-lg hover:bg-primary-600"
        >
          <Sparkles className="w-3.5 h-3.5" />
          Generate Video
        </Link>
      </div>
    </div>
  )
}

export default function Channels() {
  const { data, isLoading } = useQuery({
    queryKey: ['channels'],
    queryFn: api.getChannels,
  })

  return (
    <div>
      <PageHeader
        title="Channels"
        description="Manage your YouTube channel configurations"
      />

      {isLoading ? (
        <div className="grid grid-cols-2 gap-4">
          {Array.from({ length: 2 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : !data || data.channels.length === 0 ? (
        <EmptyState
          icon={Radio}
          title="No channels configured"
          description="Add channel YAML files to src/channel_configs/"
        />
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {data.channels.map((ch: ChannelWithStats) => (
            <ChannelCard key={ch.channel_id} channel={ch} />
          ))}
        </div>
      )}
    </div>
  )
}
