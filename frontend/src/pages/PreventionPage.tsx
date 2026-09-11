import React from 'react';
import {
  ShieldCheck,
  Award,
  GraduationCap,
  TrendingUp,
  AlertOctagon,
  CheckCircle2,
  ArrowUpRight,
  Sparkles,
  ClipboardCheck,
  AlertTriangle,
  Lightbulb,
  ArrowRight,
  Target,
  Wrench,
  Users,
  MapPin,
  Clock,
  HelpCircle,
  TrendingDown,
} from 'lucide-react';
import { AnimatedCounter } from '../components/ui/AnimatedCounter';
import { useScrollReveal } from '../hooks/useScrollReveal';
import { PreventionMetrics, SummaryKPIs, StructuredRecommendation } from '../types/warehouse';

interface PreventionPageProps {
  prevention: PreventionMetrics | null;
  summary: SummaryKPIs | null;
}

export const PreventionPage: React.FC<PreventionPageProps> = ({
  prevention,
  summary,
}) => {
  const bannerReveal = useScrollReveal();
  const coachingReveal = useScrollReveal();
  const recommendationsReveal = useScrollReveal();

  const safeRatio = summary?.risk_free_observation_ratio ?? (prevention?.safe_handling_ratio || 100.0);
  const protectedUnits = summary?.potentially_protected_units ?? (prevention?.potential_damage_prevented || 0);
  const interventionsLogged = prevention?.interventions_logged || 0;
  const recommendations: StructuredRecommendation[] = prevention?.structured_recommendations || [];
  const training = prevention?.training_opportunities || [];
  const patterns = prevention?.recurring_risk_patterns || [];

  return (
    <div className="space-y-7 animate-fade-in text-slate-800">
      {/* 1. Prevention Impact Banner: Shift from Detection to Prevention */}
      <div
        ref={bannerReveal.ref}
        className={`bg-slate-900 rounded-xl p-6 text-white border border-slate-800 shadow-md relative overflow-hidden transition-all duration-700 ${
          bannerReveal.isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
        }`}
      >
        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800 text-sky-400 text-[10px] font-mono font-bold mb-3 border border-slate-700">
            <Sparkles className="w-3.5 h-3.5 text-sky-400" />
            <span>PROACTIVE WAREHOUSE INTELLIGENCE</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-3">
            <span>Damage Detection</span>
            <span className="text-sky-400">→</span>
            <span className="text-emerald-400">Damage Prevention</span>
          </h1>
          <p className="text-slate-300 text-xs mt-2 leading-relaxed">
            CareGuard AI detects unsafe handling kinematics at early sequence stages before packaging failure or drop damage occurs, empowering warehouse supervisors to intervene and eliminate risk at the source.
          </p>
        </div>
      </div>

      {/* 2. Prevention Metrics KPI Cards with Animated Counters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex items-center justify-between">
          <div>
            <div className="text-[10px] font-bold font-mono text-slate-500 uppercase tracking-wider">
              Potentially Protected Units
            </div>
            <div className="text-2xl font-extrabold font-mono text-emerald-600 mt-1 flex items-baseline gap-1">
              <span>~</span>
              <AnimatedCounter value={protectedUnits} />
              <span className="text-xs text-slate-500 font-normal">units</span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">Estimated via timely supervisor interventions</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex items-center justify-between">
          <div>
            <div className="text-[10px] font-bold font-mono text-slate-500 uppercase tracking-wider">
              Risk-Free Handling Ratio
            </div>
            <div className="text-2xl font-extrabold font-mono text-sky-700 mt-1 flex items-baseline">
              <AnimatedCounter value={safeRatio} decimals={1} />
              <span className="text-xs ml-0.5">%</span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">Compliant handling sequences</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-sky-50 text-sky-700 border border-sky-200 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex items-center justify-between">
          <div>
            <div className="text-[10px] font-bold font-mono text-slate-500 uppercase tracking-wider">
              Supervisor Interventions Logged
            </div>
            <div className="text-2xl font-extrabold font-mono text-indigo-700 mt-1">
              <AnimatedCounter value={interventionsLogged} />
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">Logged in audit trail</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 flex items-center justify-center">
            <GraduationCap className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* 3. Structured Operational Recommendations (6-Part Schema) */}
      <div
        ref={recommendationsReveal.ref}
        className={`bg-white rounded-xl border border-slate-200 p-5 shadow-xs transition-all duration-700 ${
          recommendationsReveal.isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
        }`}
      >
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900 font-mono">
              Structured Damage Prevention Recommendations
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Root-cause analysis and operational changes derived from telemetry evidence
            </p>
          </div>
          <span className="text-[10px] font-mono bg-sky-50 text-sky-700 border border-sky-200 px-2 py-0.5 rounded font-bold">
            CAREGUARD POLICY
          </span>
        </div>

        {recommendations.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recommendations.map((rec) => (
              <div
                key={rec.id}
                className="p-4 rounded-lg border border-slate-200 bg-slate-50/60 hover:bg-white hover:border-slate-300 hover:shadow-xs transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-[9px] font-bold uppercase px-2 py-0.5 rounded font-mono ${
                      rec.priority === 'CRITICAL'
                        ? 'bg-rose-50 text-rose-700 border border-rose-200'
                        : rec.priority === 'HIGH'
                        ? 'bg-orange-50 text-orange-700 border border-orange-200'
                        : 'bg-sky-50 text-sky-700 border border-sky-200'
                    }`}>
                      {rec.priority} PRIORITY
                    </span>
                    {rec.equipment_tag && (
                      <span className="text-[10px] font-mono text-slate-500 bg-white border border-slate-200 px-2 py-0.5 rounded">
                        Suggested: {rec.equipment_tag}
                      </span>
                    )}
                  </div>

                  <h3 className="text-xs font-bold text-slate-900 mb-3">{rec.what_happened}</h3>

                  <div className="space-y-2 text-xs">
                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-bold font-mono text-slate-400 uppercase min-w-[70px]">WHERE:</span>
                      <span className="text-slate-700 font-medium">{rec.where}</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-bold font-mono text-slate-400 uppercase min-w-[70px]">WHEN:</span>
                      <span className="text-slate-600 font-mono text-[11px]">{rec.when}</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-bold font-mono text-slate-400 uppercase min-w-[70px]">WHY IT MATTERS:</span>
                      <span className="text-slate-700 leading-snug">{rec.why_it_matters}</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-bold font-mono text-sky-700 uppercase min-w-[70px]">CHANGE:</span>
                      <span className="text-sky-900 font-medium leading-snug">{rec.what_to_change}</span>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-2.5 border-t border-slate-200 text-[11px] text-emerald-800 bg-emerald-50/70 p-2 rounded">
                  <span className="font-bold block text-[10px] font-mono uppercase text-emerald-900">Expected Operational Effect:</span>
                  <span>{rec.expected_operational_effect}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center bg-slate-50 rounded-lg border border-dashed border-slate-200">
            <ShieldCheck className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
            <div className="text-xs font-bold text-slate-700">Zero High-Risk Telemetry Incidents</div>
            <p className="text-[11px] text-slate-500 mt-1 max-w-md mx-auto">
              No critical prevention recommendations required. All monitored handling operations currently comply with Godrej safe handling benchmarks.
            </p>
          </div>
        )}
      </div>

      {/* 4. Section: "WHAT SHOULD THE SUPERVISOR DO NEXT?" & Equipment Gaps */}
      <div
        ref={coachingReveal.ref}
        className={`grid grid-cols-1 lg:grid-cols-2 gap-6 transition-all duration-700 ${
          coachingReveal.isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
        }`}
      >
        {/* Left: Recommended Supervisor Coaching Opportunities */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 font-mono">
                  Recommended Supervisor Coaching
                </h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Targeted ergonomic & procedural coaching prioritized by damage risk
                </p>
              </div>
              <Users className="w-4 h-4 text-slate-400" />
            </div>

            <div className="space-y-3">
              {training.map((t) => (
                <div key={t.id} className="p-3.5 rounded-lg border border-slate-200 bg-slate-50/50 hover:bg-slate-50 transition-colors">
                  <div className="flex items-center justify-between">
                    <span className={`text-[9px] font-bold uppercase px-2 py-0.5 rounded font-mono ${
                      t.priority === 'CRITICAL' ? 'bg-rose-50 text-rose-700 border border-rose-200' : (t.priority === 'HIGH' ? 'bg-orange-50 text-orange-700 border border-orange-200' : 'bg-amber-50 text-amber-700 border border-amber-200')
                    }`}>
                      {t.priority} Priority
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono bg-white px-2 py-0.5 rounded border border-slate-200">{t.target_bay}</span>
                  </div>
                  <h4 className="text-xs font-bold text-slate-900 mt-2">{t.title}</h4>
                  <p className="text-xs text-slate-600 mt-1 leading-relaxed">{t.reason}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Shift Target: <b>Zero Unassisted Heavy Lifts</b></span>
            <span className="font-mono text-sky-600 font-semibold">Bay 1 Priority</span>
          </div>
        </div>

        {/* Right: Recurring Risk Patterns & Equipment Gaps */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 font-mono">
                  Recurring Risk Patterns & Equipment Gaps
                </h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Identified systemic bottlenecks leading to improper handling
                </p>
              </div>
              <Wrench className="w-4 h-4 text-amber-500" />
            </div>

            <div className="space-y-3">
              {patterns.map((p, idx) => (
                <div key={idx} className="p-3.5 rounded-lg border border-slate-200 bg-slate-50/50">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span className="font-bold text-slate-800 text-xs">Identified Bottleneck #{idx + 1}</span>
                    <span className="bg-white border border-slate-200 px-2 py-0.5 rounded font-mono text-[10px] font-bold text-slate-600">
                      {p.frequency}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 font-medium mt-1.5 leading-relaxed">
                    {p.pattern}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 p-3.5 rounded-lg bg-sky-50 border border-sky-100 text-xs text-sky-950 leading-relaxed">
            <div className="flex items-center gap-1.5 font-bold font-mono text-sky-900 text-[11px] uppercase mb-1">
              <Lightbulb className="w-3.5 h-3.5 text-sky-700" />
              <span>Suggested Equipment Deployment</span>
            </div>
            Deploy two additional hydraulic hand trolleys to General Staging Bay during the 14:00 - 16:00 peak dispatch window to eliminate single-person carton dragging.
          </div>
        </div>
      </div>
    </div>
  );
};

