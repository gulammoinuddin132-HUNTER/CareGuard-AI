import React from 'react';
import {
  Activity,
  AlertTriangle,
  Camera,
  ShieldCheck,
  Warehouse,
  ChevronRight,
  Boxes,
  ShieldAlert,
  MapPin,
  CheckCircle2,
  Workflow,
  Radio,
  Eye,
  ArrowRight,
  Package,
  Layers,
} from 'lucide-react';
import { RiskBadge } from '../components/ui/Badge';
import { AnimatedCounter } from '../components/ui/AnimatedCounter';
import {
  SummaryKPIs,
  WarehouseEvent,
  BehaviourDistItem,
  HourlyTrendItem,
  BayStatItem,
  PreventionMetrics,
  VideoState,
} from '../types/warehouse';

interface OverviewPageProps {
  summary: SummaryKPIs | null;
  recentIncidents: WarehouseEvent[];
  behaviourDist: BehaviourDistItem[];
  hourlyTrends: HourlyTrendItem[];
  bayStats: BayStatItem[];
  prevention: PreventionMetrics | null;
  videoState: VideoState | null;
  onNavigateToMonitoring: () => void;
  onSelectIncident: (incident: WarehouseEvent) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  summary,
  recentIncidents,
  behaviourDist,
  hourlyTrends,
  bayStats,
  prevention,
  videoState,
  onNavigateToMonitoring,
  onSelectIncident,
}) => {
  const currentRisk = videoState?.current_risk_level || 'GREEN';
  const latestEvent = recentIncidents.length > 0 ? recentIncidents[0] : (videoState?.current_event || null);

  const totalIncidents = summary?.total_events ?? 0;
  const activeSafetyEvents = summary?.active_safety_events ?? totalIncidents;
  const highRiskEvents = (summary?.critical_events ?? 0) + (summary?.high_risk_events ?? 0);
  const unitsSeen = summary?.units_seen ?? summary?.items_monitored ?? 0;
  const liveTracksCount = videoState?.active_tracks_count ?? 0;
  const safeHandlingRatio = summary?.risk_free_observation_ratio ?? (prevention?.safe_handling_ratio ?? 100.0);
  const rawQualityScore = summary?.handling_quality_score ?? 100;

  const getQualityTheme = (score: number) => {
    if (score >= 90) {
      return {
        label: 'Optimal / Safe',
        textColor: 'text-emerald-600',
        barColor: 'bg-emerald-500',
        badgeBg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      };
    }
    if (score >= 75) {
      return {
        label: 'Good / Watch',
        textColor: 'text-amber-600',
        barColor: 'bg-amber-500',
        badgeBg: 'bg-amber-50 text-amber-700 border-amber-200',
      };
    }
    if (score >= 50) {
      return {
        label: 'Needs Attention',
        textColor: 'text-orange-600',
        barColor: 'bg-orange-500',
        badgeBg: 'bg-orange-50 text-orange-700 border-orange-200',
      };
    }
    return {
      label: 'Critical Action Required',
      textColor: 'text-rose-600',
      barColor: 'bg-rose-500',
      badgeBg: 'bg-rose-50 text-rose-700 border-rose-200',
    };
  };

  const qualityTheme = getQualityTheme(rawQualityScore);

  // 5-Stage Visual Operational Flow
  const pipelineSteps = [
    {
      step: '01',
      action: 'SEE',
      title: 'Visual Ingestion',
      icon: Camera,
      desc: 'Real-time CCTV and camera feeds track material handling across dock bays.',
    },
    {
      step: '02',
      action: 'UNDERSTAND',
      title: 'Action Analysis',
      icon: Activity,
      desc: 'Tracks package trajectories, handler separation, velocities, and floor contact.',
    },
    {
      step: '03',
      action: 'ASSESS',
      title: 'Risk Evaluation',
      icon: ShieldAlert,
      desc: 'Classifies potential damage risks (drops, drags, unstable stacks, obstructions).',
    },
    {
      step: '04',
      action: 'ACT',
      title: 'Supervisor Action',
      icon: CheckCircle2,
      desc: 'Instant operational guidance: inspect goods, deploy trolleys, restack safely.',
    },
    {
      step: '05',
      action: 'PREVENT',
      title: 'Damage Prevention',
      icon: ShieldCheck,
      desc: 'Identifies recurring handling issues to eliminate damage before shipment.',
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in text-slate-800">
      {/* 1. Page Header & Live Status */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight font-sans">
              CareGuard Command Center
            </h1>
            <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-md bg-sky-50 text-sky-700 border border-sky-200">
              Live Operations
            </span>
          </div>
          <p className="text-sm sm:text-base text-slate-600 font-semibold mt-1">
            Warehouse Safety & Damage Prevention — Real-time Handling Intelligence
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 px-3.5 py-2 rounded-lg text-xs font-semibold">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-slate-700">Database: <strong className="text-slate-900">careguard.db ACTIVE</strong></span>
          </div>
          <button
            onClick={onNavigateToMonitoring}
            className="flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 text-white transition-colors shadow-xs"
          >
            <Radio className="w-4 h-4" />
            <span>Open Live Feed</span>
          </button>
        </div>
      </div>

      {/* 2. Primary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Card 1: Handling Quality */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-bold uppercase tracking-wider">Handling Quality</span>
            <ShieldCheck className="w-4 h-4 text-sky-600" />
          </div>
          <div className="my-3">
            <div className="text-3xl sm:text-4xl font-extrabold font-mono text-slate-900 flex items-baseline gap-1">
              <AnimatedCounter value={rawQualityScore} />
              <span className="text-sm font-semibold text-slate-500">/ 100</span>
            </div>
            <span className={`inline-block text-xs font-bold px-2 py-0.5 rounded mt-1.5 ${totalIncidents === 0 ? 'bg-slate-100 text-slate-700 border border-slate-200' : qualityTheme.badgeBg}`}>
              {totalIncidents === 0 ? 'No activity — baseline' : qualityTheme.label}
            </span>
          </div>
          <p className="text-xs text-slate-500 font-medium">Last 20 events</p>
        </div>

        {/* Card 2: Active Safety Events */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-bold uppercase tracking-wider">Active Safety Events</span>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </div>
          <div className="my-3">
            <div className="text-3xl sm:text-4xl font-extrabold font-mono text-slate-900">
              <AnimatedCounter value={activeSafetyEvents} />
            </div>
            <span className="inline-block text-xs font-bold text-slate-600 mt-1.5">
              {activeSafetyEvents === 0 ? 'Zero unresolved incidents' : `${activeSafetyEvents} awaiting review`}
            </span>
          </div>
          <p className="text-xs text-slate-500 font-medium">Unresolved incidents ({totalIncidents} total logged)</p>
        </div>

        {/* Card 3: High-Risk Events */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-bold uppercase tracking-wider">High-Risk Events</span>
            <ShieldAlert className="w-4 h-4 text-rose-600" />
          </div>
          <div className="my-3">
            <div className="text-3xl sm:text-4xl font-extrabold font-mono text-rose-600">
              <AnimatedCounter value={highRiskEvents} />
            </div>
            <span className="inline-block text-xs font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded mt-1.5 border border-rose-200">
              {summary?.critical_events ?? 0} Critical (RED) • {summary?.high_risk_events ?? 0} High (ORANGE)
            </span>
          </div>
          <p className="text-xs text-slate-500 font-medium">Current session</p>
        </div>

        {/* Card 4: Unique Cargo Items Seen */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-bold uppercase tracking-wider">Unique Cargo Items Seen</span>
            <Boxes className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="my-3">
            <div className="text-3xl sm:text-4xl font-extrabold font-mono text-slate-900">
              <AnimatedCounter value={unitsSeen} />
            </div>
            <span className="inline-block text-xs font-bold text-slate-600 mt-1.5">
              {unitsSeen === 0 ? 'No tracked packages' : `${unitsSeen} distinct cargo tracks`}
            </span>
          </div>
          <p className="text-xs text-slate-500 font-medium">Based on logged session tracks</p>
        </div>

        {/* Card 5: Safe Handling % */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-bold uppercase tracking-wider">Safe Handling %</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="my-3">
            {totalIncidents === 0 ? (
              <div className="text-3xl sm:text-4xl font-extrabold font-mono text-slate-400 flex items-baseline">
                —
              </div>
            ) : (
              <div className="text-3xl sm:text-4xl font-extrabold font-mono text-emerald-600 flex items-baseline gap-0.5">
                <AnimatedCounter value={safeHandlingRatio} decimals={1} />
                <span className="text-sm font-bold">%</span>
              </div>
            )}
            <span className={`inline-block text-xs font-bold px-2 py-0.5 rounded mt-1.5 ${totalIncidents === 0 ? 'bg-slate-100 text-slate-600 border border-slate-200' : 'text-emerald-700 bg-emerald-50 border border-emerald-200'}`}>
              {totalIncidents === 0 ? 'No activity' : 'Risk-free handling ratio'}
            </span>
          </div>
          <p className="text-xs text-slate-500 font-medium">Current session (all events)</p>
        </div>
      </div>

      {/* 3. Operational Sections: Recent Safety Events & Latest Incident */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Recent Safety Events Table */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-sans">
                  Recent Safety Events
                </h2>
                <p className="text-xs text-slate-500 font-medium mt-0.5">
                  Real-time handling audit trail from careguard.db
                </p>
              </div>
              <span className="text-xs font-bold font-mono px-2.5 py-1 rounded bg-slate-100 text-slate-700 border border-slate-200">
                {recentIncidents.length} Recent Event(s)
              </span>
            </div>

            <div className="mt-4 overflow-x-auto">
              {recentIncidents.length > 0 ? (
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs font-bold text-slate-500 uppercase tracking-wider font-mono">
                      <th className="py-2.5 px-3">Time</th>
                      <th className="py-2.5 px-3">Behaviour</th>
                      <th className="py-2.5 px-3">Risk Level</th>
                      <th className="py-2.5 px-3">Location</th>
                      <th className="py-2.5 px-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-sm font-medium">
                    {recentIncidents.slice(0, 6).map((inc) => (
                      <tr
                        key={inc.event_id}
                        onClick={() => onSelectIncident(inc)}
                        className="hover:bg-slate-50/80 cursor-pointer transition-colors group"
                      >
                        <td className="py-3 px-3 font-mono text-xs text-slate-600 whitespace-nowrap">
                          {inc.start_timestamp ? inc.start_timestamp.split(' ')[1] || inc.start_timestamp : 'Just now'}
                        </td>
                        <td className="py-3 px-3 font-bold text-slate-900">
                          {inc.behaviour_type.replace(/_/g, ' ')}
                        </td>
                        <td className="py-3 px-3">
                          <RiskBadge level={inc.risk_level} size="sm">
                            {inc.risk_level}
                          </RiskBadge>
                        </td>
                        <td className="py-3 px-3 text-xs text-slate-600 font-semibold">
                          {inc.loading_bay || 'Bay 01'}
                        </td>
                        <td className="py-3 px-3 text-right">
                          <span className="text-xs font-bold text-sky-600 group-hover:text-sky-700 inline-flex items-center gap-1">
                            <span>Review</span>
                            <ChevronRight className="w-3.5 h-3.5" />
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="py-12 text-center text-slate-500 space-y-2">
                  <ShieldCheck className="w-10 h-10 text-slate-400 mx-auto" />
                  <p className="text-base font-bold text-slate-700">No safety events recorded yet.</p>
                  <p className="text-xs text-slate-500">All monitored warehouse operations are running within safe parameters.</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right 1 Col: Latest Incident Breakdown (WHAT HAPPENED, WHY IT MATTERS, WHAT TO DO) */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-sans">
                Latest Incident Focus
              </h2>
              {latestEvent && (
                <RiskBadge level={latestEvent.risk_level} size="sm">
                  {latestEvent.risk_level}
                </RiskBadge>
              )}
            </div>

            {latestEvent ? (
              <div className="mt-4 space-y-4">
                <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                  <div className="flex items-center justify-between text-xs font-mono text-slate-500">
                    <span>Event: <strong className="text-slate-900">{latestEvent.event_id}</strong></span>
                    <span>{latestEvent.loading_bay || 'Bay 01'}</span>
                  </div>
                  <div className="text-base font-extrabold text-slate-900 mt-1">
                    {latestEvent.behaviour_type.replace(/_/g, ' ')}
                  </div>
                </div>

                {/* What Happened */}
                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase tracking-wider font-mono">
                    What Happened
                  </div>
                  <p className="text-sm font-semibold text-slate-800 mt-1 leading-relaxed">
                    {latestEvent.observed_behaviour || 'Unsafe material movement sequence recorded.'}
                  </p>
                </div>

                {/* Why It Matters */}
                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase tracking-wider font-mono">
                    Why It Matters
                  </div>
                  <p className="text-sm font-semibold text-slate-800 mt-1 leading-relaxed">
                    {latestEvent.potential_risk || 'Potential product breakage, carton structural failure, or packaging seam tear.'}
                  </p>
                </div>

                {/* What To Do */}
                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase tracking-wider font-mono">
                    What To Do
                  </div>
                  <p className="text-sm font-semibold text-sky-800 bg-sky-50 border border-sky-200 p-2.5 rounded-lg mt-1 leading-relaxed">
                    {latestEvent.recommended_action || 'Inspect the product, check packaging seals, and reinforce safe handling procedures.'}
                  </p>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-slate-500 space-y-2">
                <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto" />
                <p className="text-base font-bold text-slate-700">No active incidents</p>
                <p className="text-xs text-slate-500">When an event occurs, root-cause explanations and supervisor actions will appear here.</p>
              </div>
            )}
          </div>

          {latestEvent && (
            <div className="pt-4 mt-4 border-t border-slate-100">
              <button
                onClick={() => onSelectIncident(latestEvent)}
                className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs transition-colors"
              >
                <span>View Full Evidence in Safety Events</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 4. Visual Operational Process: SEE -> UNDERSTAND -> ASSESS -> ACT -> PREVENT */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="pb-3 mb-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-sans">
              CareGuard Operational Intelligence Pipeline
            </h2>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              How CareGuard AI transforms raw video into proactive damage prevention
            </p>
          </div>
          <span className="text-xs font-bold font-mono px-2.5 py-1 rounded bg-sky-50 text-sky-700 border border-sky-200">
            5-Stage Processing
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {pipelineSteps.map((step, idx) => {
            const Icon = step.icon;
            return (
              <div
                key={step.step}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-slate-50 transition-colors flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-extrabold font-mono text-sky-600 bg-sky-50 px-2 py-0.5 rounded border border-sky-200">
                      {step.step} {step.action}
                    </span>
                    <Icon className="w-4 h-4 text-slate-600" />
                  </div>
                  <div className="text-sm font-extrabold text-slate-900 mt-1">
                    {step.title}
                  </div>
                  <p className="text-xs text-slate-600 font-medium mt-1 leading-relaxed">
                    {step.desc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
