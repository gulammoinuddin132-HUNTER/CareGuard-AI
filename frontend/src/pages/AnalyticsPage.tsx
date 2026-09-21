import React, { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import {
  Layers,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Warehouse,
  ShieldAlert,
  ArrowDownCircle,
  MoveHorizontal,
  Flame,
  Boxes,
  Compass,
  Ban,
  Package,
  Share2,
  AlertOctagon,
  Sparkles,
  Footprints,
  Info,
} from 'lucide-react';
import { RiskBadge } from '../components/ui/Badge';
import { AnimatedCounter } from '../components/ui/AnimatedCounter';
import { BehaviourDistItem, BayStatItem, ShiftStatItem } from '../types/warehouse';

interface AnalyticsPageProps {
  behaviourDist: BehaviourDistItem[];
  bayStats: BayStatItem[];
  shiftStats?: ShiftStatItem[];
}

export const AnalyticsPage: React.FC<AnalyticsPageProps> = ({
  behaviourDist,
  bayStats,
  shiftStats = [],
}) => {
  const riskColors: Record<string, string> = {
    GREEN: '#10B981',
    YELLOW: '#F59E0B',
    ORANGE: '#F97316',
    RED: '#E11D48',
  };

  // Plain-language, operational descriptions for all 10 behaviours
  const simpleDescriptions: Record<string, string> = {
    PRODUCT_DROPPED: 'Product separated from the handler, moved downward, and reached the floor.',
    PRODUCT_DRAGGED: 'Product moved along the floor without lifting or using a trolley.',
    ROUGH_HANDLING: 'Package slammed or dropped abruptly with sharp deceleration impact.',
    INCORRECT_STACKING: 'Larger or heavier box placed on top of a smaller base box.',
    UNSTABLE_STACKING: 'Stacked box column leaning or tilting dangerously.',
    PLACED_OUTSIDE_DESIGNATED_AREA: 'Box left in a walking aisle or emergency exit lane.',
    HANDLED_WITHOUT_EQUIPMENT: 'Heavy box carried manually over distance without equipment.',
    PALLET_POSITIONED_INCORRECTLY: 'Pallet sticking out beyond bay lines into a traffic lane.',
    MATERIAL_PUSHED_THROWN: 'Box tossed or thrown through the air.',
    UNSAFE_LOADING_SEQUENCE: 'Lower box pulled from a stack while upper boxes remain overhead.',
  };

  const totalIncidents = behaviourDist.reduce((acc, curr) => acc + curr.count, 0);

  // Standard 10-behaviour taxonomy items
  const all10Behaviors = [
    { type: 'PRODUCT_DROPPED', name: 'Product Dropped', defaultRisk: 'RED' },
    { type: 'PRODUCT_DRAGGED', name: 'Product Dragged', defaultRisk: 'ORANGE' },
    { type: 'ROUGH_HANDLING', name: 'Rough Handling / Slam', defaultRisk: 'ORANGE' },
    { type: 'INCORRECT_STACKING', name: 'Incorrect Stacking', defaultRisk: 'ORANGE' },
    { type: 'UNSTABLE_STACKING', name: 'Unstable / Leaning Stack', defaultRisk: 'ORANGE' },
    { type: 'PLACED_OUTSIDE_DESIGNATED_AREA', name: 'Walkway Obstruction', defaultRisk: 'ORANGE' },
    { type: 'HANDLED_WITHOUT_EQUIPMENT', name: 'Heavy Manual Carry', defaultRisk: 'YELLOW' },
    { type: 'PALLET_POSITIONED_INCORRECTLY', name: 'Pallet Misaligned', defaultRisk: 'YELLOW' },
    { type: 'MATERIAL_PUSHED_THROWN', name: 'Material Thrown', defaultRisk: 'RED' },
    { type: 'UNSAFE_LOADING_SEQUENCE', name: 'Unsafe Unloading Order', defaultRisk: 'RED' },
  ];

  // Map counts from database
  const countMap = new Map<string, number>();
  behaviourDist.forEach((d) => countMap.set(d.behaviour_type, d.count));

  const chartData = all10Behaviors.map((b) => ({
    name: b.name,
    count: countMap.get(b.type) || 0,
    risk: b.defaultRisk,
  }));

  return (
    <div className="space-y-6 animate-fade-in text-slate-800">
      {/* 1. Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight font-sans">
              Behaviour Insights & Analytics
            </h1>
            <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-md bg-sky-50 text-sky-700 border border-sky-200">
              10-Behaviour Taxonomy
            </span>
          </div>
          <p className="text-sm sm:text-base text-slate-600 font-semibold mt-1">
            Breakdown of observed handling deviations across 10 warehouse safety rules in careguard.db
          </p>
        </div>

        <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 px-3.5 py-2 rounded-lg text-xs font-semibold">
          <span className="text-slate-600">Total Recorded Events:</span>
          <strong className="text-slate-900 font-mono text-sm">{totalIncidents}</strong>
        </div>
      </div>

      {/* 2. Frequency Bar Chart: 100% Identical Data to Cards */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-100">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-sans">
              Observed Event Frequency by Behaviour
            </h2>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Exact event count recorded in careguard.db (zero events shown as 0)
            </p>
          </div>
          <span className="text-xs font-mono font-bold text-slate-600 bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
            {totalIncidents} Total Events
          </span>
        </div>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
              <XAxis
                dataKey="name"
                angle={-25}
                textAnchor="end"
                interval={0}
                tick={{ fontSize: 11, fill: '#475569', fontWeight: 600 }}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 12, fill: '#64748B', fontWeight: 600 }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0F172A',
                  border: 'none',
                  borderRadius: '8px',
                  color: '#FFFFFF',
                  fontSize: '12px',
                  fontWeight: 600,
                }}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={riskColors[entry.risk] || '#0284C7'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 3. 10 Supported Behaviours Grid */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="pb-3 mb-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-sans">
              10 Supported Handling Behaviours
            </h2>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Real observed counts from active database vs standard taxonomy definition
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          {all10Behaviors.map((b) => {
            const count = countMap.get(b.type) || 0;
            const desc = simpleDescriptions[b.type] || 'Standard warehouse handling check.';
            return (
              <div
                key={b.type}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-white hover:border-slate-300 transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <RiskBadge level={b.defaultRisk as any} size="sm">
                      {b.defaultRisk}
                    </RiskBadge>
                    <span className="text-xl font-extrabold font-mono text-slate-900">
                      {count}
                    </span>
                  </div>
                  <div className="text-sm font-extrabold text-slate-900 mt-2">
                    {b.name}
                  </div>
                  <p className="text-xs text-slate-600 font-medium mt-1 leading-relaxed">
                    {desc}
                  </p>
                </div>
                <div className="mt-3 pt-2 border-t border-slate-200/60 flex items-center justify-between text-[11px] font-mono text-slate-500">
                  <span>Status:</span>
                  <span className={count > 0 ? 'text-amber-700 font-bold' : 'text-slate-400 font-semibold'}>
                    {count > 0 ? `${count} Logged` : '0 Recorded'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. Shift Analytics Table (Real Database Timestamps) */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="pb-3 mb-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-sans">
              Shift Risk Comparison
            </h2>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Derived strictly from timestamped incident records in careguard.db
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase tracking-wider font-mono">
                <th className="py-3 px-4">Shift Name</th>
                <th className="py-3 px-4">Total Incidents</th>
                <th className="py-3 px-4">Critical (RED)</th>
                <th className="py-3 px-4">High Risk (ORANGE)</th>
                <th className="py-3 px-4">Handling Quality</th>
                <th className="py-3 px-4">Safe Ratio</th>
                <th className="py-3 px-4">Operational Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm font-medium">
              {shiftStats.map((s) => (
                <tr key={s.shift_id} className="hover:bg-slate-50">
                  <td className="py-3.5 px-4 font-bold text-slate-900">
                    {s.shift}
                  </td>
                  <td className="py-3.5 px-4 font-mono font-bold text-slate-800">
                    {s.incidents}
                  </td>
                  <td className="py-3.5 px-4 font-mono font-bold text-rose-600">
                    {s.critical_count}
                  </td>
                  <td className="py-3.5 px-4 font-mono font-bold text-orange-600">
                    {s.high_risk_count}
                  </td>
                  <td className="py-3.5 px-4 font-mono font-bold text-slate-900">
                    {s.handling_quality_score}/100
                  </td>
                  <td className="py-3.5 px-4 font-mono text-emerald-700 font-bold">
                    {s.risk_free_ratio}
                  </td>
                  <td className="py-3.5 px-4">
                    <span className={`text-xs font-bold px-2.5 py-1 rounded ${
                      s.incidents === 0
                        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                        : (s.status === 'CRITICAL' ? 'bg-rose-50 text-rose-800 border border-rose-200' : 'bg-amber-50 text-amber-800 border border-amber-200')
                    }`}>
                      {s.incidents === 0 ? 'No Recorded Incidents' : s.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
