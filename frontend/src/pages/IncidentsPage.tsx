import React, { useState } from 'react';
import {
  AlertTriangle,
  Clock,
  MapPin,
  Eye,
  CheckCircle2,
  Search,
  Filter,
  ShieldAlert,
  Send,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  RotateCcw,
  User,
  Boxes,
  ExternalLink,
} from 'lucide-react';
import { RiskBadge } from '../components/ui/Badge';
import { WarehouseEvent } from '../types/warehouse';

interface IncidentsPageProps {
  incidents: WarehouseEvent[];
  selectedIncident: WarehouseEvent | null;
  onSelectIncident: (incident: WarehouseEvent | null) => void;
  onLogAction: (eventId: string, note: string) => Promise<void>;
}

type SourceFilter = 'all' | 'real' | 'simulated';

export const IncidentsPage: React.FC<IncidentsPageProps> = ({
  incidents,
  selectedIncident,
  onSelectIncident,
  onLogAction,
}) => {
  const [activeTab, setActiveTab] = useState<SourceFilter>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [actionNote, setActionNote] = useState<string>('');
  const [submittingAction, setSubmittingAction] = useState<boolean>(false);
  const [actionSuccess, setActionSuccess] = useState<boolean>(false);

  // Filter and sort incidents strictly newest first
  const filteredIncidents = incidents
    .filter((item) => {
      if (activeTab === 'real' && item.is_simulated) return false;
      if (activeTab === 'simulated' && !item.is_simulated) return false;
      if (severityFilter !== 'all' && item.risk_level !== severityFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchType = item.behaviour_type.toLowerCase().includes(q);
        const matchId = item.event_id.toLowerCase().includes(q);
        const matchLoc = (item.loading_bay || 'Bay 01').toLowerCase().includes(q);
        if (!matchType && !matchId && !matchLoc) return false;
      }
      return true;
    })
    .sort((a, b) => (b.start_timestamp || '').localeCompare(a.start_timestamp || ''));

  const realCount = incidents.filter((i) => !i.is_simulated).length;
  const simCount = incidents.filter((i) => i.is_simulated).length;

  const getEvidenceUrl = (path?: string | null) => {
    if (!path) return null;
    if (path.startsWith('/api/evidence/')) return path;
    const fname = path.split(/[/\\]/).pop();
    return fname ? `/api/evidence/${fname}` : null;
  };

  const handleQuickAction = async (actionText: string) => {
    if (!selectedIncident) return;
    setSubmittingAction(true);
    try {
      await onLogAction(selectedIncident.event_id, actionText);
      setActionSuccess(true);
      setTimeout(() => setActionSuccess(false), 2500);
    } finally {
      setSubmittingAction(false);
    }
  };

  const handleCustomActionSubmit = async () => {
    if (!selectedIncident || !actionNote.trim()) return;
    setSubmittingAction(true);
    try {
      await onLogAction(selectedIncident.event_id, actionNote);
      setActionNote('');
      setActionSuccess(true);
      setTimeout(() => setActionSuccess(false), 2500);
    } finally {
      setSubmittingAction(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in text-slate-800">
      {/* 1. Header & Source Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight font-sans">
              Safety Events Audit Log
            </h1>
            <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 border border-slate-200 font-mono">
              {incidents.length} Total Events
            </span>
          </div>
          <p className="text-sm sm:text-base text-slate-600 font-semibold mt-1">
            Official operational log of material handling deviations, kinematic evidence, and supervisor actions
          </p>
        </div>

        {/* Source Filter Tabs */}
        <div className="flex items-center bg-slate-100 p-1 rounded-lg border border-slate-200 text-xs font-bold">
          <button
            onClick={() => setActiveTab('all')}
            className={`px-3 py-1.5 rounded-md transition-colors ${
              activeTab === 'all'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            All Events ({incidents.length})
          </button>
          <button
            onClick={() => setActiveTab('real')}
            className={`px-3 py-1.5 rounded-md transition-colors ${
              activeTab === 'real'
                ? 'bg-white text-emerald-800 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Live Camera ({realCount})
          </button>
          <button
            onClick={() => setActiveTab('simulated')}
            className={`px-3 py-1.5 rounded-md transition-colors ${
              activeTab === 'simulated'
                ? 'bg-white text-amber-800 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Simulated ({simCount})
          </button>
        </div>
      </div>

      {/* 2. Search & Severity Filter Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search events by ID, behaviour type, or bay location..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 text-slate-800 font-medium"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-bold text-slate-500 uppercase font-mono">Severity:</span>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="text-xs font-bold bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:border-sky-500"
          >
            <option value="all">All Severities</option>
            <option value="RED">CRITICAL (RED)</option>
            <option value="ORANGE">HIGH RISK (ORANGE)</option>
            <option value="YELLOW">WARNING (YELLOW)</option>
            <option value="GREEN">SAFE (GREEN)</option>
          </select>
        </div>
      </div>

      {/* 3. Main Workspace: Event Table + Detailed Evidence Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Incident Table */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
          {filteredIncidents.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase tracking-wider font-mono">
                    <th className="py-3 px-4">Event ID</th>
                    <th className="py-3 px-4">Time</th>
                    <th className="py-3 px-4">Behaviour</th>
                    <th className="py-3 px-4">Severity</th>
                    <th className="py-3 px-4">Bay</th>
                    <th className="py-3 px-4">Participants</th>
                    <th className="py-3 px-4 text-right">Evidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-sm font-medium">
                  {filteredIncidents.map((inc) => {
                    const isSelected = selectedIncident?.event_id === inc.event_id;
                    return (
                      <tr
                        key={inc.event_id}
                        onClick={() => onSelectIncident(inc)}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-sky-50/80 border-l-4 border-l-sky-600'
                            : 'hover:bg-slate-50'
                        }`}
                      >
                        <td className="py-3.5 px-4 font-mono text-xs font-bold text-slate-900 whitespace-nowrap">
                          {inc.event_id}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-xs text-slate-600 whitespace-nowrap">
                          {inc.start_timestamp ? inc.start_timestamp.split(' ')[1] || inc.start_timestamp : 'Just now'}
                        </td>
                        <td className="py-3.5 px-4 font-bold text-slate-900">
                          {inc.behaviour_type.replace(/_/g, ' ')}
                        </td>
                        <td className="py-3.5 px-4">
                          <RiskBadge level={inc.risk_level} size="sm">
                            {inc.risk_level}
                          </RiskBadge>
                        </td>
                        <td className="py-3.5 px-4 text-xs font-semibold text-slate-600">
                          {inc.loading_bay || 'Bay 01'}
                        </td>
                        <td className="py-3.5 px-4 text-xs font-mono text-slate-600">
                          {inc.person_track_id ? `H#${inc.person_track_id}` : '—'} • {inc.product_track_id ? `P#${inc.product_track_id}` : '—'}
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded uppercase tracking-wider ${
                              inc.status === 'RESOLVED'
                                ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                : 'bg-amber-50 text-amber-700 border border-amber-200'
                            }`}>
                              {inc.status === 'RESOLVED' ? 'Resolved' : 'Open'}
                            </span>
                            <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                              inc.evidence_frame_path
                                ? 'bg-sky-50 text-sky-700 border border-sky-200'
                                : 'bg-slate-100 text-slate-500'
                            }`}>
                              {inc.evidence_frame_path ? 'Snapshot' : 'Logged'}
                            </span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-16 text-center text-slate-500 space-y-2">
              <ShieldCheck className="w-12 h-12 text-slate-400 mx-auto" />
              <p className="text-lg font-bold text-slate-800">No safety events recorded yet.</p>
              <p className="text-xs text-slate-500">
                When warehouse handling violations are detected by the vision engine, they will be logged here.
              </p>
            </div>
          )}
        </div>

        {/* Right 1 Col: Evidence Snapshot & Action Form */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          {selectedIncident ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div>
                  <span className="text-xs font-mono text-slate-500">Event Details:</span>
                  <div className="text-base font-extrabold text-slate-900 font-mono">
                    {selectedIncident.event_id}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded uppercase tracking-wider ${
                    selectedIncident.status === 'RESOLVED'
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                  }`}>
                    {selectedIncident.status === 'RESOLVED' ? 'Resolved' : 'Open'}
                  </span>
                  <RiskBadge level={selectedIncident.risk_level} size="sm">
                    {selectedIncident.risk_level}
                  </RiskBadge>
                </div>
              </div>

              {/* Evidence Image Snapshot */}
              {selectedIncident.evidence_frame_path ? (
                <div className="rounded-lg overflow-hidden border border-slate-200 bg-slate-950 aspect-video relative">
                  <img
                    src={getEvidenceUrl(selectedIncident.evidence_frame_path) || ''}
                    alt="Event Evidence"
                    className="w-full h-full object-contain"
                  />
                  <div className="absolute bottom-2 left-2 bg-black/75 px-2 py-0.5 rounded text-[10px] font-mono text-white">
                    {selectedIncident.loading_bay || 'Bay 01'} • {selectedIncident.start_timestamp}
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-6 text-center text-slate-500">
                  <Boxes className="w-8 h-8 mx-auto text-slate-400 mb-1" />
                  <p className="text-xs font-bold text-slate-700">Telemetry Logged</p>
                  <p className="text-[11px] text-slate-500">Kinematic tracking vector captured without cropped snapshot.</p>
                </div>
              )}

              {/* What Happened */}
              <div>
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wider font-mono">
                  What Happened
                </div>
                <p className="text-sm font-semibold text-slate-800 mt-1 leading-relaxed">
                  {selectedIncident.observed_behaviour}
                </p>
              </div>

              {/* Why It Matters */}
              <div>
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wider font-mono">
                  Why It Matters
                </div>
                <p className="text-sm font-semibold text-slate-800 mt-1 leading-relaxed">
                  {selectedIncident.potential_risk}
                </p>
              </div>

              {/* Recommended Action */}
              <div>
                <div className="text-xs font-bold text-slate-500 uppercase tracking-wider font-mono">
                  Recommended Action
                </div>
                <p className="text-sm font-semibold text-sky-800 bg-sky-50 border border-sky-200 p-2.5 rounded-lg mt-1 leading-relaxed">
                  {selectedIncident.recommended_action}
                </p>
              </div>

              {/* Existing Supervisor Action Note */}
              {selectedIncident.operator_action && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs space-y-1">
                  <div className="flex items-center gap-1 font-bold text-emerald-900">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Supervisor Resolution Logged</span>
                  </div>
                  <p className="text-emerald-800 font-medium">{selectedIncident.operator_action}</p>
                  {selectedIncident.resolved_at && (
                    <span className="text-[10px] text-emerald-600 block font-mono">
                      Timestamp: {selectedIncident.resolved_at}
                    </span>
                  )}
                </div>
              )}

              {/* Supervisor Corrective Action Logger */}
              <div className="pt-3 border-t border-slate-100 space-y-2">
                <div className="text-xs font-bold text-slate-700 font-mono">
                  {selectedIncident.status === 'RESOLVED' ? 'Update Action Note:' : 'Log Corrective Action Note:'}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="e.g. 'Inspected package contents, no seal damage found.'..."
                    value={actionNote}
                    onChange={(e) => setActionNote(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleCustomActionSubmit();
                    }}
                    className="flex-1 text-xs px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-sky-500 font-medium"
                  />
                  <button
                    disabled={!actionNote.trim() || submittingAction}
                    onClick={handleCustomActionSubmit}
                    className="px-3 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-1"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Log</span>
                  </button>
                </div>
                {actionSuccess && (
                  <p className="text-xs font-bold text-emerald-600 flex items-center gap-1 mt-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Action logged successfully into careguard.db</span>
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="py-16 text-center text-slate-500 space-y-2">
              <Eye className="w-10 h-10 text-slate-400 mx-auto" />
              <p className="text-base font-bold text-slate-700">Select a Safety Event</p>
              <p className="text-xs text-slate-500">
                Click any row in the audit log to review its kinematic evidence, root cause, and log corrective notes.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
