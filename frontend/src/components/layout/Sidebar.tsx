import React from 'react';
import {
  LayoutDashboard,
  Video,
  AlertCircle,
  BarChart3,
  ShieldCheck,
  BotMessageSquare,
  Settings,
  Zap,
} from 'lucide-react';
import careguardLogo from '../../assets/careguard-logo.png';

export type TabType =
  | 'overview'
  | 'monitoring'
  | 'incidents'
  | 'analytics'
  | 'prevention'
  | 'assistant'
  | 'settings';

interface SidebarProps {
  currentTab: TabType;
  onSelectTab: (tab: TabType) => void;
  criticalCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  criticalCount,
}) => {
  const navItems: Array<{
    id: TabType;
    label: string;
    icon: any;
    badge?: number | null;
  }> = [
    {
      id: 'overview',
      label: 'Command Center',
      icon: LayoutDashboard,
    },
    {
      id: 'monitoring',
      label: 'Live Monitoring',
      icon: Video,
    },
    {
      id: 'incidents',
      label: 'Safety Events',
      icon: AlertCircle,
      badge: criticalCount > 0 ? criticalCount : null,
    },
    {
      id: 'analytics',
      label: 'Behaviour Insights',
      icon: BarChart3,
    },
    {
      id: 'prevention',
      label: 'Prevention',
      icon: ShieldCheck,
    },
    {
      id: 'assistant',
      label: 'Safety Copilot',
      icon: BotMessageSquare,
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: Settings,
    },
  ];

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between h-[calc(100vh-69px)] sticky top-[69px] text-slate-200 select-none shadow-sm">
      <div className="p-4 space-y-6 overflow-y-auto">
        {/* Brand Banner Card in Sidebar */}
        <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-slate-950/80 border border-slate-800 shadow-inner">
          <img
            src={careguardLogo}
            alt="CareGuard AI"
            className="w-8 h-8 object-contain rounded-md bg-white p-0.5"
          />
          <div className="leading-tight">
            <div className="text-sm font-extrabold text-white">CareGuard AI</div>
            <div className="text-[11px] text-sky-400 font-semibold font-mono">Operations Suite</div>
          </div>
        </div>

        {/* Navigation Items with larger, bold typography */}
        <nav className="space-y-1.5">
          <div className="px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-400 font-mono">
            Navigation
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-3 rounded-xl text-left transition-all group relative ${
                  isActive
                    ? 'bg-sky-600 text-white font-bold shadow-md shadow-sky-600/20'
                    : 'text-slate-300 hover:bg-slate-800/80 hover:text-white font-semibold'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-5 h-5 transition-colors ${isActive ? 'text-white' : 'text-slate-400 group-hover:text-slate-200'}`} />
                  <span className="text-sm tracking-wide">{item.label}</span>
                </div>
                {item.badge && (
                  <span className="bg-rose-500 text-white text-xs font-black font-mono px-2 py-0.5 rounded-full border border-rose-400 shadow-xs">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer Info: Core 5-Stage Operational Flow */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/60">
        <div className="bg-slate-900/90 rounded-xl p-3 border border-slate-800">
          <div className="flex items-center gap-1.5 text-sky-400 font-mono font-bold text-[11px] uppercase">
            <Zap className="w-3.5 h-3.5 text-sky-400" />
            <span>OPERATIONAL FLOW</span>
          </div>
          <p className="text-[11px] text-slate-300 mt-1 font-mono leading-relaxed font-bold">
            SEE → UNDERSTAND → ASSESS → ACT → PREVENT
          </p>
        </div>
      </div>
    </aside>
  );
};
