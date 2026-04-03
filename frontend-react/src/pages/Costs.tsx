import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { formatCost } from '@/lib/utils'
import { PageHeader } from '@/components/layout/PageHeader'
import { StatCard } from '@/components/ui/StatCard'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { DollarSign, TrendingUp, Server } from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts'

const PERIOD_OPTIONS = [
  { value: 7, label: '7 days' },
  { value: 30, label: '30 days' },
  { value: 90, label: '90 days' },
]

const PIE_COLORS = ['#635bff', '#00d4aa', '#f5a623', '#ff4d4f', '#3b82f6']

export default function Costs() {
  const [days, setDays] = useState(30)

  const { data: costs, isLoading: costsLoading } = useQuery({
    queryKey: ['costs', days],
    queryFn: () => api.getCosts({ days }),
  })

  const { data: dailyCosts } = useQuery({
    queryKey: ['daily-costs', days],
    queryFn: () => api.getDailyCosts(days),
  })

  const { data: byService } = useQuery({
    queryKey: ['costs-by-service', days],
    queryFn: () => api.getCostsByService(days),
  })

  const totalRuns = costs?.by_channel.reduce((sum, ch) => sum + ch.run_count, 0) || 0
  const avgPerRun = totalRuns > 0 ? (costs?.total_cost_usd || 0) / totalRuns : 0
  const projectedMonthly = days <= 30
    ? ((costs?.total_cost_usd || 0) / days) * 30
    : (costs?.total_cost_usd || 0)

  return (
    <div>
      <PageHeader
        title="Cost Analytics"
        description="Track and optimize your pipeline spending"
      />

      {/* Period Selector */}
      <div className="flex gap-1 mb-6 p-1 bg-surface rounded-lg border border-border w-fit">
        {PERIOD_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setDays(opt.value)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
              days === opt.value
                ? 'bg-primary-500 text-white'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Stats */}
      {costsLoading ? (
        <div className="grid grid-cols-3 gap-4 mb-6">
          {Array.from({ length: 3 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatCard
            label={`${days}-Day Total`}
            value={formatCost(costs?.total_cost_usd)}
            icon={DollarSign}
            iconColor="text-primary-500 bg-primary-50"
          />
          <StatCard
            label="Avg per Run"
            value={formatCost(avgPerRun)}
            icon={TrendingUp}
            iconColor="text-emerald-600 bg-emerald-50"
          />
          <StatCard
            label="Monthly Projected"
            value={formatCost(projectedMonthly)}
            icon={Server}
            iconColor="text-amber-600 bg-amber-50"
          />
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Daily Cost Chart */}
        <div className="col-span-2 bg-surface rounded-xl border border-border p-5">
          <h3 className="text-sm font-semibold mb-4">Daily Costs</h3>
          {dailyCosts && dailyCosts.data.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={dailyCosts.data}>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => v.slice(5)}
                />
                <YAxis
                  yAxisId="cost"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => `$${v}`}
                  orientation="left"
                />
                <YAxis
                  yAxisId="runs"
                  tick={{ fontSize: 11 }}
                  orientation="right"
                />
                <Tooltip
                  formatter={(val, name) => [
                    name === 'cost' ? `$${Number(val).toFixed(4)}` : val,
                    name === 'cost' ? 'Cost' : 'Runs'
                  ]}
                  labelFormatter={(l) => `Date: ${l}`}
                />
                <Bar yAxisId="runs" dataKey="run_count" fill="#e0e7ff" radius={[4, 4, 0, 0]} />
                <Bar yAxisId="cost" dataKey="cost" fill="#635bff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[280px] flex items-center justify-center text-sm text-text-tertiary">
              No pipeline runs in this period
            </div>
          )}
        </div>

        {/* Service Breakdown */}
        <div className="bg-surface rounded-xl border border-border p-5">
          <h3 className="text-sm font-semibold mb-4">By Service</h3>
          {byService && byService.services.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie
                    data={byService.services}
                    dataKey="total_cost_usd"
                    nameKey="service"
                    cx="50%"
                    cy="50%"
                    innerRadius={45}
                    outerRadius={70}
                    paddingAngle={3}
                  >
                    {byService.services.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(val) => `$${Number(val).toFixed(4)}`} />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-3 space-y-2">
                {byService.services.map((svc, i) => (
                  <div key={svc.service} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                      />
                      <span className="text-text-secondary">{svc.service}</span>
                    </div>
                    <span className="font-mono font-medium">{formatCost(svc.total_cost_usd)}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-sm text-text-tertiary">
              Mostly local — minimal costs
            </div>
          )}
        </div>
      </div>

      {/* Channel Cost Table */}
      {costs && costs.by_channel.length > 0 && (
        <div className="mt-6 bg-surface rounded-xl border border-border overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border-light">
            <h3 className="text-sm font-semibold">Cost by Channel</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-secondary text-left">
                <th className="px-5 py-2.5 text-xs font-semibold text-text-secondary uppercase">Channel</th>
                <th className="px-5 py-2.5 text-xs font-semibold text-text-secondary uppercase text-right">Runs</th>
                <th className="px-5 py-2.5 text-xs font-semibold text-text-secondary uppercase text-right">Total Cost</th>
                <th className="px-5 py-2.5 text-xs font-semibold text-text-secondary uppercase text-right">Avg/Run</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-light">
              {costs.by_channel.map((ch) => (
                <tr key={ch.channel_id}>
                  <td className="px-5 py-3 font-medium">{ch.channel_id}</td>
                  <td className="px-5 py-3 text-right text-text-secondary">{ch.run_count}</td>
                  <td className="px-5 py-3 text-right font-mono">{formatCost(ch.total_cost_usd)}</td>
                  <td className="px-5 py-3 text-right font-mono text-text-secondary">
                    {formatCost(ch.run_count > 0 ? ch.total_cost_usd / ch.run_count : 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
