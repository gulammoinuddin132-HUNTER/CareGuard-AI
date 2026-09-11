import React from 'react';
import {
  ShieldAlert,
  Boxes,
  TrendingDown,
  ArrowRight,
  Clock,
  MapPin,
  Activity,
  Play,
  ShieldCheck,
  Eye,
  CheckCircle2,
  AlertTriangle,
  Camera,
  Layers,
  Cpu,
  Zap,
  Target,
  FileSearch,
  Sparkles,
  Award,
  Warehouse,
  ChevronRight,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
} from 'recharts';
import { Card } from '../components/ui/Card';
import { RiskBadge } from '../components/ui/Badge';
import { AnimatedCounter } from '../components/ui/AnimatedCounter';
import { useScrollReveal } from '../hooks/useScrollReveal';
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
  const currentEvent = videoState?.current_event;

  const totalIncidents = summary?.total_events ?? 0;
  const criticalEvents = (summary?.critical_events ?? 0) + (summary?.high_risk_events ?? 0);
  const totalMonitoredItems = summary?.items_monitored ?? (videoState?.active_tracks_count ?? 0);
  const riskFreeRatio = summary?.risk_free_observation_ratio ?? (prevention?.safe_handling_ratio ?? 100.0);
  const handlingQuality = summary?.handling_quality_score ?? 100;

  // Scroll reveal hooks for storytelling sections
  const heroReveal = useScrollReveal();
  const pipelineReveal = useScrollReveal();
  const liveStreamReveal = useScrollReveal();
  const analyticsReveal = useScrollReveal();

  const pipelineSteps = [
    {
      step: '01',
      title: 'VIDEO INGESTION',
      icon: Camera,
      desc: 'Receives live camera feeds and recorded warehouse footage.',
      tag: '30 FPS Ingestion',
    },
    {
      step: '02',
      title: 'AI PERCEPTION',
      icon: Cpu,
      desc: 'Detects handlers, cartons/products, pallets and material-handling equipment.',
      tag: 'Multi-Class Perception',
    },
    {
      step: '03',
      title: 'OBJECT TRACKING',
      icon: Layers,
      desc: 'Maintains persistent entity tracks and motion information.',
      tag: 'Continuous Motion',
    },
    {
      step: '04',
      title: 'BEHAVIOUR UNDERSTANDING',
      icon: Activity,
      desc: 'Analyses multi-frame actions to identify warehouse handling patterns.',
      tag: '10 Behaviours',
    },
    {
      step: '05',
      title: 'DAMAGE RISK DETECTION',
      icon: AlertTriangle,
      desc: 'Classifies potential material-damage and handling risk.',
      tag: 'Non-Punitive Safety',
    },
    {
      step: '06',
      title: 'SUPERVISOR INTERVENTION',
      icon: Zap,
      desc: 'Provides immediate, behaviour-specific corrective guidance.',
      tag: 'Targeted Guidance',
    },
    {
      step: '07',
      title: 'DAMAGE PREVENTION',
      icon: ShieldCheck,
      desc: 'Identifies recurring patterns and recommends process/equipment improvements.',
      tag: 'Zero Damage Goal',
    },
  ];

  const hasTrendData = hourlyTrends.some((h) => (h.risk_events ?? h.total ?? 0) > 0);

  return (
    <div className="space-y-8 animate-fade-in text-slate-800">
      {/* ========================================================================= */}
      {/* 1. HERO EXECUTIVE STATUS: Warehouse Condition in < 5 Seconds */}
      {/* ========================================================================= */}
      <div
        ref={heroReveal.ref}
        className={`bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-md text-white transition-all duration-700 ${
          heroReveal.isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
        }`}
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-slate-800">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-slate-800 text-sky-400 border border-slate-700 font-mono text-[10px] uppercase font-bold tracking-wider mb-2">
              <Sparkles className="w-3.5 h-3.5 text-sky-400" />
              <span>CareGuard AI • Warehouse Safety Intelligence</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              See Risk. <span className="text-sky-400">Prevent Damage.</span>
            </h1>
            <p className="text-xs sm:text-sm text-slate-300 mt-1 max-w-2xl leading-relaxed">
              AI-powered video intelligence that helps warehouse teams identify risky handling behaviour before damage occurs.
            </p>
          </div>

          {/* Operational Status Module */}
          <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-4 flex items-center gap-4 shrink-0 shadow-inner">
            <div className="space-y-1">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
                CURRENT OPERATIONAL STATUS
              </div>
              <div className="flex items-center gap-2">
                <span className={`w-3 h-3 rounded-full animate-pulse ${
                  currentRisk === 'GREEN' ? 'bg-emerald-500' : (currentRisk === 'YELLOW' ? 'bg-amber-500' : (currentRisk === 'ORANGE' ? 'bg-orange-500' : 'bg-rose-500'))
                }`} />
                <span className="text-base font-bold font-mono text-white">
                  {currentRisk === 'GREEN' ? 'SAFE' : (currentRisk === 'YELLOW' ? 'ATTENTION' : (currentRisk === 'ORANGE' ? 'HIGH RISK' : 'CRITICAL'))}
                </span>
              </div>
              <div className="text-[10px] text-slate-500 font-mono">
                {videoState?.fps || 0} FPS • {videoState?.active_tracks_count || 0} Active Tracks
              </div>
            </div>
            <button
              onClick={onNavigateToMonitoring}
              className="bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold px-3 py-2 rounded-md transition-colors flex items-center gap-1.5 shrink-0"
            >
              <span>Live Console</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Top Operational Metrics with Grounded Telemetry & Tooltips */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 pt-5">
          <div
            className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 cursor-help group"
            title="Severity-weighted operational index based on recorded handling-risk events (100 baseline: RED=-10, ORANGE=-5, YELLOW=-2, GREEN=0)."
          >
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block truncate">
              HANDLING QUALITY INDEX
            </span>
            <div className="text-xl font-extrabold font-mono text-emerald-400 mt-1 flex items-baseline gap-1">
              <AnimatedCounter value={handlingQuality} />
              <span className="text-[11px] text-slate-500 font-normal">/100</span>
            </div>
            <span className="text-[10px] text-slate-500 block mt-0.5 font-mono">Internal Quality Index</span>
          </div>

          <div
            className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 cursor-help group"
            title="Count of actively tracked cargo items and warehouse entities observed in the active session."
          >
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block truncate">
              ITEMS / ENTITIES MONITORED
            </span>
            <div className="text-xl font-extrabold font-mono text-sky-400 mt-1">
              <AnimatedCounter value={totalMonitoredItems} />
            </div>
            <span className="text-[10px] text-slate-500 block mt-0.5 font-mono">Active Tracked Units</span>
          </div>

          <div
            className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 cursor-help group"
            title="Total handling-risk events recorded in the current session/database."
          >
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block truncate">
              RISK EVENTS
            </span>
            <div className="text-xl font-extrabold font-mono text-white mt-1">
              <AnimatedCounter value={totalIncidents} />
            </div>
            <span className="text-[10px] text-slate-500 block mt-0.5 font-mono">Recorded CV Incidents</span>
          </div>

          <div
            className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 cursor-help group"
            title="Count of RED (Critical) and ORANGE (High Risk) safety violations requiring immediate intervention."
          >
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block truncate">
              HIGH / CRITICAL EVENTS
            </span>
            <div className="text-xl font-extrabold font-mono text-rose-400 mt-1">
              <AnimatedCounter value={criticalEvents} />
            </div>
            <span className="text-[10px] text-rose-500 block mt-0.5 font-mono">RED & ORANGE Tiers</span>
          </div>

          <div
            className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 cursor-help group"
            title="Share of monitored handling observations operating within safe kinematic boundaries."
          >
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block truncate">
              RISK-FREE OBSERVATION RATIO
            </span>
            <div className="text-xl font-extrabold font-mono text-emerald-400 mt-1 flex items-baseline">
              <AnimatedCounter value={riskFreeRatio} decimals={1} />
              <span className="text-xs ml-0.5">%</span>
            </div>
            <span className="text-[10px] text-slate-500 block mt-0.5 font-mono">Safe Kinematics Share</span>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 2. SCROLL STORYTELLING: FROM VIDEO TO UNDERSTANDING */}
      {/* ========================================================================= */}
      <div
        ref={pipelineReveal.ref}
        className={`bg-white rounded-xl border border-slate-200 p-5 shadow-xs transition-all duration-700 ${
          pipelineReveal.isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
        }`}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-4 pb-3 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900 font-mono">
                FROM VIDEO TO UNDERSTANDING
              </h2>
              <span className="text-[10px] font-mono bg-sky-50 text-sky-700 border border-sky-200 px-2 py-0.5 rounded font-bold">
                END-TO-END PIPELINE
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">
              How CareGuard AI transforms raw warehouse pixels into early proactive damage prevention
            </p>
          </div>
          <span className="text-[10px] text-slate-400 font-mono">
            7-Stage Intelligent Processing
          </span>
        </div>

        {/* 7 Staggered Pipeline Nodes */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-7 gap-2.5">
          {pipelineSteps.map((p, idx) => {
            const Icon = p.icon;
            return (
              <div
                key={p.step}
                className={`p-3 rounded-lg border border-slate-200 bg-slate-50/50 hover:bg-sky-50/30 hover:border-sky-200 transition-all flex flex-col justify-between group ${
                  pipelineReveal.isVisible ? `animate-fade-in-up stagger-${idx + 1}` : ''
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono font-bold text-slate-400 group-hover:text-sky-600">
                      #{p.step}
                    </span>
                    <Icon className="w-4 h-4 text-slate-400 group-hover:text-sky-600 transition-colors" />
                  </div>
                  <h3 className="text-[11px] font-bold text-slate-900 mt-2 leading-tight">
                    {p.title}
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-1 leading-snug">
                    {p.desc}
                  </p>
                </div>
                <div className="mt-3 pt-2 border-t border-slate-200/60">
                  <span className="text-[9px] font-mono font-bold text-slate-600 bg-white border border-slate-200 px-1.5 py-0.5 rounded block text-center truncate">
                    {p.tag}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 3. LIVE INTELLIGENCE VIEWPORT & RESPONSIBLE AI BREAKDOWN (60/40 SPLIT) */}
      {/* ========================================================================= */}
      <div
        ref={liveStreamReveal.ref}
        className={`grid grid-cols-1 xl:grid-cols-12 gap-6 transition-all duration-700 ${
          liveStreamReveal.isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
        }`}
      >
        {/* Left 7-Cols: Live MJPEG Video Stream with High-Tech Frame */}
        <div className="xl:col-span-7 space-y-3">
          <div className="bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-md relative aspect-[16/10] flex items-center justify-center group">
            <img
              src="/api/video/feed"
              alt="CareGuard Live Video Feed"
              className="w-full h-full object-cover"
              onError={(e) => {
                (e.target as HTMLImageElement).src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480"><rect width="640" height="480" fill="%230b1120"/><text x="50%" y="50%" fill="%2364748b" font-family="sans-serif" font-size="14" text-anchor="middle">CareGuard AI Perception Engine Active</text></svg>';
              }}
            />

            {/* Top-Left Telemetry Overlay */}
            <div className="absolute top-3 left-3 bg-slate-900/90 backdrop-blur-sm border border-slate-700/80 rounded-lg px-3 py-1.5 text-white text-xs flex items-center gap-2.5 font-mono shadow-sm">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-bold text-[11px] text-white">LIVE</span>
              </div>
              <span className="text-slate-600">|</span>
              <span className="text-slate-300 text-[11px]">{videoState?.fps || 0} FPS</span>
              <span className="text-slate-600">|</span>
              <span className="text-sky-300 text-[11px]">{videoState?.active_tracks_count || 0} Tracks</span>
            </div>

            {/* Top-Right Risk Indicator */}
            <div className="absolute top-3 right-3">
              <RiskBadge level={currentRisk} size="md">
                {currentRisk === 'GREEN' ? 'SAFE' : (currentRisk === 'YELLOW' ? 'ATTENTION' : (currentRisk === 'ORANGE' ? 'HIGH RISK' : 'CRITICAL'))}
              </RiskBadge>
            </div>

            {/* Bottom Floating Bar */}
            <div className="absolute bottom-3 inset-x-3 bg-slate-900/90 backdrop-blur-sm border border-slate-700/80 rounded-lg px-3 py-2 flex items-center justify-between text-xs text-white">
              <div className="flex items-center gap-2 font-mono text-[11px]">
                <MapPin className="w-3.5 h-3.5 text-sky-400" />
                <span className="text-slate-300">ACTIVE MONITORING ZONE: BAY 01 • GENERAL STAGING</span>
              </div>
              <span className="text-slate-400 text-[10px] font-mono">
                {videoState?.last_frame_timestamp ? videoState.last_frame_timestamp.split(' ')[1] : 'ACTIVE'}
              </span>
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-slate-500 px-1">
            <span className="font-mono text-[11px]">
              Source: <b>{videoState?.video_file || (videoState?.source_type === 'camera' ? 'Webcam #0' : 'Synthetic Stream')}</b>
            </span>
            <button
              onClick={onNavigateToMonitoring}
              className="text-sky-600 hover:text-sky-700 font-semibold flex items-center gap-1 text-xs"
            >
              <span>Switch Sources & Presets</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Right 5-Cols: LIVE SAFETY EVENT & 3-TIER RESPONSIBLE AI PANEL */}
        <div className="xl:col-span-5 flex flex-col justify-between space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex-1 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-100">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 font-mono">
                    LIVE SAFETY EVENT
                  </h3>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Responsible AI Sequence: Behaviour → Risk → Action
                  </p>
                </div>
                {currentEvent && (
                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded font-mono uppercase ${
                    currentEvent.is_simulated
                      ? 'bg-amber-50 text-amber-800 border border-amber-200'
                      : 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                  }`}>
                    {currentEvent.is_simulated ? 'SIMULATED SCENARIO' : 'REAL CV DETECTED'}
                  </span>
                )}
              </div>

              {currentEvent ? (
                <div className="space-y-3">
                  {/* Event Title & Risk Level */}
                  <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex items-start justify-between">
                    <div>
                      <span className="text-[10px] font-mono text-slate-400 block">{currentEvent.event_id}</span>
                      <h4 className="text-xs font-bold text-slate-900 mt-0.5">{currentEvent.behaviour_type}</h4>
                      <span className="text-[11px] text-slate-500 font-mono mt-0.5 block">{currentEvent.loading_bay || 'Bay 01 • General Staging'}</span>
                    </div>
                    <RiskBadge level={currentEvent.risk_level} size="md">
                      {currentEvent.risk_level}
                    </RiskBadge>
                  </div>

                  {/* Tier 1: Observed Behaviour */}
                  <div className="p-3 rounded-lg bg-sky-50/60 border border-sky-100">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-sky-900">
                      <span className="w-4 h-4 rounded bg-sky-200 text-sky-800 flex items-center justify-center text-[10px] font-mono">1</span>
                      <span>Observed Behaviour (Sensor Telemetry)</span>
                    </div>
                    <p className="text-xs text-slate-700 mt-1 leading-relaxed font-medium">
                      {currentEvent.observed_behaviour}
                    </p>
                  </div>

                  {/* Tier 2: Potential Damage Risk */}
                  <div className="p-3 rounded-lg bg-amber-50/60 border border-amber-100">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-amber-900">
                      <span className="w-4 h-4 rounded bg-amber-200 text-amber-800 flex items-center justify-center text-[10px] font-mono">2</span>
                      <span>Potential Damage Risk</span>
                    </div>
                    <p className="text-xs text-slate-700 mt-1 leading-relaxed font-medium">
                      {currentEvent.potential_risk}
                    </p>
                  </div>

                  {/* Tier 3: Recommended Supervisor Action */}
                  <div className="p-3 rounded-lg bg-emerald-50/60 border border-emerald-100">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-900">
                      <span className="w-4 h-4 rounded bg-emerald-200 text-emerald-800 flex items-center justify-center text-[10px] font-mono">3</span>
                      <span>Recommended Supervisor Action</span>
                    </div>
                    <p className="text-xs text-slate-700 mt-1 leading-relaxed font-medium">
                      {currentEvent.recommended_action}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="py-12 text-center text-slate-400 space-y-2">
                  <ShieldCheck className="w-10 h-10 mx-auto text-emerald-500" />
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">SAFE OPERATIONAL STATE</h4>
                  <p className="text-xs text-slate-500">Normal material handling detected. No unsafe kinematics observed across monitored zones.</p>
                </div>
              )}
            </div>

            {currentEvent && (
              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[11px] text-slate-500 font-mono">
                  Confidence: <b>{(currentEvent.confidence * 100).toFixed(0)}%</b>
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onSelectIncident(currentEvent)}
                    className="text-xs font-semibold px-3 py-1.5 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-800 transition-colors"
                  >
                    View Evidence
                  </button>
                  <button
                    onClick={onNavigateToMonitoring}
                    className="text-xs font-semibold px-3 py-1.5 rounded-md bg-sky-600 hover:bg-sky-700 text-white transition-colors"
                  >
                    Live Console
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 4. OPERATIONAL ANALYTICS: Shift Risk Trend & Zone Operational Health */}
      {/* ========================================================================= */}
      <div
        ref={analyticsReveal.ref}
        className={`grid grid-cols-1 lg:grid-cols-3 gap-6 transition-all duration-700 ${
          analyticsReveal.isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
        }`}
      >
        {/* Left 2-Cols: Shift Risk Trend Area Chart */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 font-mono">
                Shift Risk Trend
              </h3>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Shows how recorded handling-risk events vary across operating hours/shifts
              </p>
            </div>
            <span className="text-[10px] font-mono text-slate-400">Timestamped Telemetry</span>
          </div>

          <div className="h-64 w-full">
            {hasTrendData ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={hourlyTrends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0284c7" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#0284c7" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="hour" stroke="#64748b" fontSize={10} />
                  <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#ffffff',
                      borderColor: '#cbd5e1',
                      borderRadius: '0.5rem',
                      fontSize: '12px',
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="risk_events"
                    name="Risk Events"
                    stroke="#0284c7"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#riskGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400">
                <ShieldCheck className="w-8 h-8 text-emerald-500 mb-2" />
                <p className="text-xs font-semibold text-slate-700">No risk events recorded in this period.</p>
                <p className="text-[11px] text-slate-400 mt-0.5 max-w-sm">
                  Operations across morning and afternoon shifts remain within safe kinematic boundaries.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right 1-Col: Zone Operational Health */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 font-mono">
                  Zone Risk Health
                </h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Real-time condition across tracked warehouse zones
                </p>
              </div>
              <Warehouse className="w-4 h-4 text-slate-400" />
            </div>

            <div className="space-y-3">
              {bayStats.map((bay) => {
                const health = bay.health_score ?? Math.max(0, 100 - (bay.incident_count * 8));
                return (
                  <div
                    key={bay.bay_id}
                    className="p-3 rounded-lg border border-slate-200 bg-slate-50/50 flex items-center justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-bold text-slate-900">{bay.name}</span>
                        <span className="text-[10px] text-slate-400 font-mono">{bay.bay_id}</span>
                      </div>
                      <div className="text-[11px] text-slate-500 mt-0.5">
                        {bay.incident_count} event(s) • {bay.status}
                      </div>
                    </div>
                    <div className="text-right">
                      <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded ${
                        health >= 85
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : (health >= 70 ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-rose-50 text-rose-700 border border-rose-200')
                      }`}>
                        {health}% Health
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-4 p-2.5 rounded-lg bg-sky-50 border border-sky-100 text-[11px] text-sky-900">
            <span className="font-bold block">Supervisor Guidance:</span>
            {totalIncidents > 0
              ? 'Ensure Bay 1 staging buffer is cleared periodically and hand trolleys are allocated to prevent floor dragging.'
              : 'All monitored staging and transit zones are operating within optimal safety clearance.'}
          </div>
        </div>
      </div>
    </div>
  );
};
