import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api, type ChannelWithStats } from '@/lib/api'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/layout/PageHeader'
import { Sparkles, AlertTriangle } from 'lucide-react'

export default function Trigger() {
  const navigate = useNavigate()
  const [topic, setTopic] = useState('')
  const [channelId, setChannelId] = useState('')
  const [error, setError] = useState('')

  const { data: channelsData } = useQuery({
    queryKey: ['channels'],
    queryFn: api.getChannels,
  })

  const triggerMutation = useMutation({
    mutationFn: () => api.triggerPipeline(topic, channelId),
    onSuccess: (data) => {
      navigate(`/pipelines/${data.workflow_id}`)
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const selectedChannel = channelsData?.channels.find(
    (ch: ChannelWithStats) => ch.channel_id === channelId
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!topic.trim()) { setError('Enter a topic'); return }
    if (!channelId) { setError('Select a channel'); return }
    triggerMutation.mutate()
  }

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="New Video"
        description="Start a new video generation pipeline"
      />

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Topic */}
        <div className="bg-surface rounded-xl border border-border p-5">
          <label className="block text-sm font-semibold mb-2">Topic</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g., 2026년 AI 트렌드 Top 5"
            className="w-full px-4 py-3 text-base border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-primary-200 focus:border-primary-400 placeholder:text-text-tertiary"
            autoFocus
          />
        </div>

        {/* Channel Selection */}
        <div className="bg-surface rounded-xl border border-border p-5">
          <label className="block text-sm font-semibold mb-3">Channel</label>
          <div className="grid grid-cols-2 gap-3">
            {channelsData?.channels.map((ch: ChannelWithStats) => (
              <button
                key={ch.channel_id}
                type="button"
                onClick={() => setChannelId(ch.channel_id)}
                className={cn(
                  'text-left p-4 rounded-lg border-2 transition-all',
                  channelId === ch.channel_id
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-border hover:border-gray-300'
                )}
              >
                <p className="text-sm font-semibold">{ch.channel_id}</p>
                <p className="text-xs text-text-secondary mt-0.5">
                  {ch.niche} / {ch.language.toUpperCase()}
                </p>
                <div className="mt-2 space-y-0.5 text-xs text-text-tertiary">
                  <p>LLM: {ch.llm_model}</p>
                  <p>Image: {ch.image_model}</p>
                  <p>TTS: {ch.tts_model}</p>
                  <p>Video: {ch.video_model}</p>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className={cn(
                    'text-xs px-1.5 py-0.5 rounded',
                    ch.vgen_enabled ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-600'
                  )}>
                    {ch.vgen_enabled ? 'Cloud Video' : 'Local Only'}
                  </span>
                  <span className="text-xs text-text-tertiary">
                    ~{ch.vgen_enabled ? '$2.50' : '$0.00'}/video
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Cost Warning */}
        {selectedChannel?.vgen_enabled && (
          <div className="flex items-start gap-3 p-4 bg-amber-50 rounded-lg border border-amber-200">
            <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-800">Estimated cost: ~$2.50</p>
              <p className="text-xs text-amber-600 mt-0.5">
                This channel uses fal.ai for video generation. Ken Burns channels cost $0.
              </p>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <p className="text-sm text-danger">{error}</p>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={triggerMutation.isPending}
          className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 bg-primary-500 text-white text-base font-semibold rounded-lg hover:bg-primary-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {triggerMutation.isPending ? (
            <>
              <Sparkles className="w-5 h-5 animate-spin" />
              Starting...
            </>
          ) : (
            <>
              <Sparkles className="w-5 h-5" />
              Generate Video
            </>
          )}
        </button>
      </form>
    </div>
  )
}
