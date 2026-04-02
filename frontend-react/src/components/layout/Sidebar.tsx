import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import {
  LayoutDashboard,
  Play,
  DollarSign,
  Radio,
  Settings,
  Clapperboard,
} from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/pipelines', icon: Play, label: 'Pipelines' },
  { to: '/costs', icon: DollarSign, label: 'Costs' },
  { to: '/channels', icon: Radio, label: 'Channels' },
]

export function Sidebar() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 30000,
  })

  const statusDot =
    health?.status === 'ok'
      ? 'bg-green-400'
      : health?.status === 'degraded'
        ? 'bg-yellow-400'
        : 'bg-red-400'

  const statusLabel =
    health?.status === 'ok'
      ? 'All operational'
      : health?.status === 'degraded'
        ? 'Degraded'
        : health
          ? 'Error'
          : 'Checking...'

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-60 bg-sidebar flex flex-col z-50">
      {/* Logo */}
      <div className="px-5 py-5 flex items-center gap-2.5">
        <Clapperboard className="w-7 h-7 text-primary-400" />
        <span className="text-lg font-semibold text-white tracking-tight">
          Studio
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 mt-2 space-y-0.5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-[13.5px] font-medium transition-colors ${
                isActive
                  ? 'bg-sidebar-active text-sidebar-text-active'
                  : 'text-sidebar-text hover:bg-sidebar-hover hover:text-sidebar-text-active'
              }`
            }
          >
            <item.icon className="w-[18px] h-[18px]" />
            {item.label}
          </NavLink>
        ))}

        <div className="my-3 border-t border-white/10" />

        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2 rounded-lg text-[13.5px] font-medium transition-colors ${
              isActive
                ? 'bg-sidebar-active text-sidebar-text-active'
                : 'text-sidebar-text hover:bg-sidebar-hover hover:text-sidebar-text-active'
            }`
          }
        >
          <Settings className="w-[18px] h-[18px]" />
          Settings
        </NavLink>
      </nav>

      {/* Health footer */}
      <div className="px-5 py-4 border-t border-white/10">
        <div className="flex items-center gap-2 text-xs text-sidebar-text">
          <span className={`w-2 h-2 rounded-full ${statusDot}`} />
          {statusLabel}
        </div>
      </div>
    </aside>
  )
}
