import React from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  GraduationCap,
  Boxes,
  MapPin,
  Clock,
  ArrowRight,
  AlertTriangle,
  Lightbulb,
  Wrench,
} from 'lucide-react';
import { AnimatedCounter } from '../components/ui/AnimatedCounter';
import { PreventionMetrics, SummaryKPIs, StructuredRecommendation } from '../types/warehouse';

interface PreventionPageProps {
  prevention: PreventionMetrics | null;
  summary: SummaryKPIs | null;
}

export const PreventionPage: React.FC<PreventionPageProps> = ({
  prevention,
  summary,
}) => {
  const safeRatio = summary?.risk_free_observation_ratio ?? (prevention?.safe_handling_ratio || 100.0);
  const protectedUnits = summary?.potentially_protected_units ?? (prevention?.potential_damage_prevented || 0);
  const interventionsLogged = prevention?.interventions_logged || 0;
  const recommendations: StructuredRecommendation[] = prevention?.structured_recommendations || [];
  const training = prevention?.training_opportunities || [];
  const patterns = prevention?.recurring_risk_patterns || [];

  return (
    <div className="space-y-6 animate-fade-in text-slate-800">
      {/* 1. Header Banner */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight font-sans">
              Damage Prevention
            </h1>
            <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200">
              Process Improvement
            </span>
          </div>
          <p className="text-sm sm:text-base text-slate-600 font-semibold mt-1">
            Use recent safety events to identify repeated handling problems and practical fixes before packages are damaged
          </p>
        </div>
      </div>

      {/* 2. KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Potentially Protected Units */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex items-center justify-between">
          <div>
            <div className="text-xs font-bold font-mono text-slate-500 uppercase tracking-wider">
              Potentially Protected Units
            </div>
            <div className="text-3xl font-extrabold font-mono text-emerald-600 mt-2 flex items-baseline gap-1">
              <span>~</span>
              <AnimatedCounter value={protectedUnits} />
              <span className="text-xs text-slate-500 font-medium">units</span>
            </div>
            <p className="text-xs text-slate-500 font-medium mt-1">
              Cargo protected through timely supervisor intervention
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center justify-center shrink-0">
            <ShieldCheck className="w-6 h-6" />
          </div>
        </div>

        {/* Safe Handling % */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex items-center justify-between">
          <div>
            <div className="text-xs font-bold font-mono text-slate-500 uppercase tracking-wider">
              Safe Handling Ratio
            </div>
            {(summary?.total_events ?? 0) === 0 ? (
              <div className="text-3xl font-extrabold font-mono text-slate-400 mt-2">
                —
              </div>
            ) : (
              <div className="text-3xl font-extrabold font-mono text-sky-700 mt-2 flex items-baseline gap-0.5">
                <AnimatedCounter value={safeRatio} decimals={1} />
                <span className="text-sm font-bold">%</span>
              </div>
            )}
            <p className="text-xs text-slate-500 font-medium mt-1">
              {(summary?.total_events ?? 0) === 0 ? 'No handling activity recorded yet' : 'Compliant handling cycles without drops or dragging'}
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-sky-50 text-sky-700 border border-sky-200 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-6 h-6" />
          </div>
        </div>

        {/* Supervisor Actions */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex items-center justify-between">
          <div>
            <div className="text-xs font-bold font-mono text-slate-500 uppercase tracking-wider">
              Supervisor Actions
            </div>
            <div className="text-3xl font-extrabold font-mono text-indigo-700 mt-2">
              <AnimatedCounter value={interventionsLogged} />
            </div>
            <p className="text-xs text-slate-500 font-medium mt-1">
              Actions logged in safety audit trail
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-700 border border-indigo-200 flex items-center justify-center shrink-0">
            <GraduationCap className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* 3. Practical Prevention Fixes (Evidence-Backed) */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-100">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-sans">
              Practical Prevention Fixes
            </h2>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              What problem occurred, why it matters, and what to change based on actual events
            </p>
          </div>
          <span className="text-xs font-mono font-bold text-slate-700 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
            {recommendations.length} Active Recommendation(s)
          </span>
        </div>

        {recommendations.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recommendations.map((rec) => (
              <div
                key={rec.id}
                className="p-5 rounded-xl border border-slate-200 bg-slate-50/70 hover:bg-white hover:border-slate-300 transition-all flex flex-col justify-between space-y-3"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold font-mono text-slate-500">
                      {rec.id} • {rec.where}
                    </span>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                      rec.priority === 'CRITICAL'
                        ? 'bg-rose-50 text-rose-700 border border-rose-200'
                        : 'bg-amber-50 text-amber-700 border border-amber-200'
                    }`}>
                      {rec.priority} Priority
                    </span>
                  </div>

                  {/* Problem */}
                  <div className="mt-2">
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider font-mono">
                      Repeated Problem
                    </div>
                    <div className="text-base font-extrabold text-slate-900 mt-0.5">
                      {rec.what_happened}
                    </div>
                  </div>

                  {/* Why it matters */}
                  <div className="mt-2">
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider font-mono">
                      Why It Matters
                    </div>
                    <p className="text-sm font-semibold text-slate-700 mt-0.5 leading-relaxed">
                      {rec.why_it_matters}
                    </p>
                  </div>

                  {/* What to change */}
                  <div className="mt-2">
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider font-mono">
                      What To Change
                    </div>
                    <p className="text-sm font-bold text-sky-900 bg-sky-50 border border-sky-200 p-2.5 rounded-lg mt-0.5 leading-relaxed">
                      {rec.what_to_change}
                    </p>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-200/60 flex items-center justify-between text-xs font-semibold text-slate-600">
                  <span>Expected Benefit: <strong>{rec.expected_operational_effect}</strong></span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-12 text-center text-slate-500 space-y-2">
            <Wrench className="w-10 h-10 text-slate-400 mx-auto" />
            <p className="text-base font-bold text-slate-800">
              Not enough data to recommend equipment changes yet.
            </p>
            <p className="text-xs text-slate-500">
              When repeated handling issues (such as dragging or drops) are recorded, specific fixes will appear here.
            </p>
          </div>
        )}
      </div>

      {/* 4. Recurring Risk Patterns & Coaching Opportunities */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Recurring Risk Patterns */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="pb-3 mb-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-sans">
                  Repeated Risk Patterns
                </h2>
                <p className="text-xs text-slate-500 font-medium mt-0.5">
                  Handling patterns observed more than once in the active session
                </p>
              </div>
            </div>

            {patterns.length > 0 ? (
              <div className="space-y-3">
                {patterns.map((p, idx) => (
                  <div
                    key={idx}
                    className="p-3.5 rounded-lg border border-slate-200 bg-slate-50 flex items-start justify-between gap-3"
                  >
                    <div>
                      <div className="text-sm font-bold text-slate-900">
                        {p.pattern}
                      </div>
                      <div className="text-xs text-slate-600 font-medium mt-0.5">
                        Location: <strong>{p.zone || 'Staging Bay (Bay 1)'}</strong>
                      </div>
                    </div>
                    <span className="text-xs font-bold font-mono bg-amber-50 text-amber-800 border border-amber-200 px-2.5 py-1 rounded whitespace-nowrap">
                      {p.frequency}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-12 text-center text-slate-500 space-y-2">
                <ShieldCheck className="w-8 h-8 text-emerald-500 mx-auto" />
                <p className="text-base font-bold text-slate-800">No repeated risk pattern identified yet.</p>
                <p className="text-xs text-slate-500">
                  Warehouse operations are currently operating without recurring bottlenecks.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right: Supervisor Coaching Priorities */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="pb-3 mb-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-sans">
                  Supervisor Coaching Priorities
                </h2>
                <p className="text-xs text-slate-500 font-medium mt-0.5">
                  Targeted brief coaching topics derived from actual handler deviations
                </p>
              </div>
            </div>

            {training.length > 0 ? (
              <div className="space-y-3">
                {training.map((t) => (
                  <div
                    key={t.id}
                    className="p-3.5 rounded-lg border border-slate-200 bg-slate-50 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-bold text-slate-900">
                        {t.title}
                      </div>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                        t.priority === 'CRITICAL'
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}>
                        {t.priority}
                      </span>
                    </div>
                    <p className="text-xs text-slate-700 font-semibold leading-relaxed">
                      Reason: {t.reason}
                    </p>
                    <div className="text-[11px] font-mono text-slate-500">
                      Target Area: {t.target_bay}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-12 text-center text-slate-500 space-y-2">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
                <p className="text-base font-bold text-slate-800">No training interventions required right now.</p>
                <p className="text-xs text-slate-500">
                  Handlers are adhering to standard safe handling procedures.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
