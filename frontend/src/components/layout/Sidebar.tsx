import React from 'react';
import {
  LayoutDashboard,
  Video,
  AlertCircle,
  BarChart3,
  ShieldAlert,
  BotMessageSquare,
  Settings,
  HelpCircle,
  Zap,
  Layers,
} from 'lucide-react';

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
  const navSections = [
    {
      group: 'REAL-TIME OPERATIONS',
      items: [
        {
          id: 'overview' as TabType,
          label: 'Command Center',
          icon: LayoutDashboard,
          description: 'Executive Status & KPIs',
        },
        {
          id: 'monitoring' as TabType,
          label: 'Live Monitoring',
          icon: Video,
          description: 'CV Stream & Event Breakdown',
        },
        {
          id: 'incidents' as TabType,
          label: 'Incident Audit',
          icon: AlertCircle,
          badge: criticalCount > 0 ? criticalCount : null,
          description: 'Evidence & Action Logs',
        },
      ],
    },
    {
      group: 'OPERATIONAL INTELLIGENCE',
      items: [
        {
          id: 'analytics' as TabType,
          label: '10-Behaviour Intelligence',
          icon: BarChart3,
          description: 'Understand Actions, Not Objects',
        },
        {
          id: 'prevention' as TabType,
          label: 'Damage Prevention Insights',
          icon: ShieldAlert,
          description: 'Root Cause & Equipment Gaps',
        },
      ],
    },
    {
      group: 'AI COPILOT & SYSTEM',
      items: [
        {
          id: 'assistant' as TabType,
          label: 'CareGuard Safety Copilot',
          icon: BotMessageSquare,
          description: 'Grounded Warehouse Safety Copilot',
        },
        {
          id: 'settings' as TabType,
          label: 'Detection & Kinematic Settings',
          icon: Settings,
          description: 'Motion & Spatial Tolerances',
        },
      ],
    },
  ];

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between h-[calc(100vh-61px)] sticky top-[61px] text-slate-300 select-none">
      <div className="p-3 space-y-4 overflow-y-auto">
        {navSections.map((section, sIdx) => (
          <div key={sIdx} className="space-y-1">
            <div className="px-3 py-1 text-[9px] font-bold uppercase tracking-wider text-slate-500 font-mono">
              {section.group}
            </div>
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onSelectTab(item.id)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-all group relative ${
                    isActive
                      ? 'bg-slate-800 text-white font-semibold border border-slate-700 shadow-sm'
                      : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200 font-medium'
                  }`}
                >
                  {isActive && (
                    <span className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r bg-sky-500" />
                  )}
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4 h-4 transition-colors ${isActive ? 'text-sky-400' : 'text-slate-500 group-hover:text-slate-300'}`} />
                    <div>
                      <div className="text-xs leading-tight">{item.label}</div>
                      <div className="text-[10px] text-slate-500 font-normal leading-tight mt-0.5">{item.description}</div>
                    </div>
                  </div>
                  {item.badge && (
                    <span className="bg-rose-600 text-white text-[10px] font-bold font-mono px-1.5 py-0.5 rounded-full border border-rose-500">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Footer Info: Responsible AI Sequence */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/40">
        <div className="bg-slate-850 rounded-lg p-2.5 border border-slate-800 text-[11px]">
          <div className="flex items-center gap-1.5 text-sky-400 font-mono font-bold text-[10px] uppercase">
            <Zap className="w-3 h-3 text-sky-400" />
            <span>CORE PIPELINE</span>
          </div>
          <p className="text-[10px] text-slate-400 mt-1 font-mono leading-relaxed">
            SEE → UNDERSTAND → ASSESS → INTERVENE → PREVENT
          </p>
        </div>
      </div>
    </aside>
  );
};
