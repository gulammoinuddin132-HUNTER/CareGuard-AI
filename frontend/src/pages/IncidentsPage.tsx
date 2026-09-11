import React, { useState } from 'react';
import {
  AlertTriangle,
  Clock,
  MapPin,
  Eye,
  CheckCircle,
  FileCheck,
  Search,
  Filter,
  Layers,
  ChevronRight,
  ShieldAlert,
  Send,
  Sparkles,
  Zap,
  RotateCcw,
} from 'lucide-react';
import { Card } from '../components/ui/Card';
import { RiskBadge } from '../components/ui/Badge';
import { WarehouseEvent, RiskLevel } from '../types/warehouse';

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

  // Filter and sort incidents strictly newest first (start_timestamp DESC)
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
    <div className="space-y-5 animate-fade-in text-slate-800">
      {/* 1. Header & Source Selection Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
            INCIDENT AUDIT & SUPERVISOR INVESTIGATION WORKSPACE
          </h2>
          <p className="text-[11px] text-slate-500 mt-0.5">
            Audit detected risk sequences, review visual evidence frames, and record corrective interventions
          </p>
        </div>

        {/* Source Filter Tabs */}
        <div className="flex items-center gap-1 bg-slate-200/80 p-1 rounded-lg border border-slate-300/80 text-xs">
          <button
            onClick={() => setActiveTab('all')}
            className={`px-3 py-1 rounded-md font-semibold transition-all ${
              activeTab === 'all'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            All Events ({incidents.length})
          </button>
          <button
            onClick={() => setActiveTab('real')}
            className={`px-3 py-1 rounded-md font-semibold flex items-center gap-1.5 transition-all ${
              activeTab === 'real'
                ? 'bg-emerald-600 text-white shadow-xs'
                : 'text-emerald-700 hover:text-emerald-900 hover:bg-emerald-50'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-300" />
            <span>Real CV ({realCount})</span>
          </button>
          <button
            onClick={() => setActiveTab('simulated')}
            className={`px-3 py-1 rounded-md font-semibold flex items-center gap-1.5 transition-all ${
              activeTab === 'simulated'
                ? 'bg-amber-600 text-white shadow-xs'
                : 'text-amber-700 hover:text-amber-900 hover:bg-amber-50'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-300" />
            <span>Simulated ({simCount})</span>
          </button>
        </div>
      </div>

      {/* 2. Search & Severity Filter Bar */}
      <div className="bg-white rounded-lg border border-slate-200 p-3 flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center gap-2 flex-1 max-w-md bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1.5 text-xs">
          <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <input
            type="text"
            placeholder="Search by event ID, behaviour, or bay..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-transparent focus:outline-none text-slate-800 placeholder:text-slate-400"
          />
        </div>

        {/* Severity Filter Pills */}
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-[10px] font-bold text-slate-500 uppercase font-mono mr-1">Severity:</span>
          {['all', 'RED', 'ORANGE', 'YELLOW'].map((sev) => (
            <button
              key={sev}
              onClick={() => setSeverityFilter(sev)}
              className={`px-2.5 py-1 rounded text-[11px] font-mono font-bold transition-all ${
                severityFilter === sev
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {sev === 'all' ? 'ALL' : sev}
            </button>
          ))}
        </div>
      </div>

      {/* 3. Investigation Grid: Event Cards List (Left) + Detail Drawer (Right) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
        {/* Left Column: High-Density Event Cards List */}
        <div className="xl:col-span-6 space-y-2.5 max-h-[calc(100vh-260px)] overflow-y-auto pr-1">
          {filteredIncidents.length > 0 ? (
            filteredIncidents.map((event) => {
              const isSelected = selectedIncident?.event_id === event.event_id;
              return (
                <div
                  key={event.event_id}
                  onClick={() => onSelectIncident(event)}
                  className={`p-3 rounded-lg border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                    isSelected
                      ? 'bg-sky-50/60 border-sky-400 ring-1 ring-sky-400 shadow-xs'
                      : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="w-16 h-12 bg-slate-900 rounded overflow-hidden shrink-0 border border-slate-800 flex items-center justify-center relative">
                      {getEvidenceUrl(event.evidence_frame_path) ? (
                        <img
                          src={getEvidenceUrl(event.evidence_frame_path)!}
                          alt={event.behaviour_type}
                          className="w-full h-full object-contain bg-black"
                          onError={(e) => {
                            const target = e.target as HTMLImageElement;
                            target.style.display = 'none';
                          }}
                        />
                      ) : (
                        <span className="text-[8px] font-mono text-slate-500">NO IMG</span>
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] font-mono font-bold text-slate-400">{event.event_id}</span>
                        {event.is_simulated ? (
                          <span className="text-[8px] font-bold font-mono px-1 rounded bg-amber-50 text-amber-800 border border-amber-200 uppercase">
                            SIM
                          </span>
                        ) : (
                          <span className="text-[8px] font-bold font-mono px-1 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 uppercase">
                            REAL CV
                          </span>
                        )}
                      </div>
                      <h4 className="text-xs font-bold text-slate-900 mt-0.5 leading-snug">{event.behaviour_type}</h4>
                      <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                        {event.loading_bay || 'Bay 01'} • {event.start_timestamp.split(' ')[1] || event.start_timestamp}
                      </p>
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <RiskBadge level={event.risk_level} size="sm">
                      {event.risk_level}
                    </RiskBadge>
                    <span className="text-[10px] font-mono text-slate-400 block mt-1">
                      {(event.confidence * 100).toFixed(0)}% conf
                    </span>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-slate-400 space-y-1">
              <ShieldAlert className="w-8 h-8 mx-auto text-slate-300" />
              <p className="text-xs font-medium">No matching incidents found for the selected filter.</p>
            </div>
          )}
        </div>

        {/* Right Column: Sliding Investigation Detail Drawer */}
        <div className="xl:col-span-6 bg-white rounded-lg border border-slate-200 p-4 shadow-xs space-y-4 sticky top-[75px]">
          {selectedIncident ? (
            <div className="space-y-4 animate-fade-in">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-slate-400">{selectedIncident.event_id}</span>
                    {selectedIncident.is_simulated ? (
                      <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 uppercase font-mono">
                        SIMULATED SCENARIO
                      </span>
                    ) : (
                      <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 uppercase font-mono">
                        REAL CV DETECTED
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-bold text-slate-900 mt-1">{selectedIncident.behaviour_type}</h3>
                </div>
                <RiskBadge level={selectedIncident.risk_level} size="md">
                  {selectedIncident.risk_level}
                </RiskBadge>
              </div>

              {/* Entity Context Bar */}
              <div className="grid grid-cols-3 gap-2 bg-slate-50 p-2.5 rounded-lg border border-slate-200 font-mono text-[10px]">
                <div>
                  <span className="text-slate-400 block uppercase">HANDLER</span>
                  <span className="font-bold text-slate-800">
                    {selectedIncident.person_track_id ? `Track #${selectedIncident.person_track_id}` : 'N/A'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block uppercase">PRODUCT</span>
                  <span className="font-bold text-slate-800">
                    {selectedIncident.product_track_id ? `Track #${selectedIncident.product_track_id}` : 'N/A'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block uppercase">CONFIDENCE</span>
                  <span className="font-bold text-sky-600">
                    {(selectedIncident.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Evidence Snapshot */}
              <div className="bg-slate-950 rounded-lg overflow-hidden border border-slate-800 aspect-video flex items-center justify-center relative">
                {getEvidenceUrl(selectedIncident.evidence_frame_path) ? (
                  <img
                    src={getEvidenceUrl(selectedIncident.evidence_frame_path)!}
                    alt="Incident Evidence"
                    className="w-full h-full object-contain bg-black"
                    onError={(e) => {
                      const target = e.target as HTMLImageElement;
                      target.style.display = 'none';
                      const parent = target.parentElement;
                      if (parent && !parent.querySelector('.evidence-fallback')) {
                        const fallback = document.createElement('div');
                        fallback.className = 'evidence-fallback text-center p-6 text-slate-400 space-y-1';
                        fallback.innerHTML = '<div class="text-xs font-mono font-bold text-amber-400">EVIDENCE FRAME UNAVAILABLE</div><div class="text-[11px] text-slate-500">Evidence frame snapshot not yet written or pending buffer flush</div>';
                        parent.appendChild(fallback);
                      }
                    }}
                  />
                ) : (
                  <div className="text-center p-6 text-slate-400 space-y-1">
                    <div className="text-xs font-mono font-bold text-amber-400">EVIDENCE FRAME UNAVAILABLE</div>
                    <div className="text-[11px] text-slate-500">No snapshot recorded for this event</div>
                  </div>
                )}
                <div className="absolute bottom-2 left-2 bg-slate-900/90 text-white text-[10px] font-mono px-2 py-0.5 rounded border border-slate-700">
                  {selectedIncident.loading_bay || 'Bay 01'} • {selectedIncident.start_timestamp}
                </div>
              </div>

              {/* 3-Tier Responsible AI Breakdown */}
              <div className="space-y-2.5">
                <div className="p-3 rounded-lg bg-sky-50/60 border border-sky-100">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-sky-800 block">
                    1. Observed Behaviour (Kinematic Sensor Data)
                  </span>
                  <p className="text-xs text-slate-700 font-medium mt-1 leading-relaxed">
                    {selectedIncident.observed_behaviour}
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-amber-50/60 border border-amber-100">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-amber-800 block">
                    2. Potential Damage Risk (Failure Mode)
                  </span>
                  <p className="text-xs text-slate-700 font-medium mt-1 leading-relaxed">
                    {selectedIncident.potential_risk}
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-emerald-50/60 border border-emerald-100">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-emerald-800 block">
                    3. Recommended Corrective Action
                  </span>
                  <p className="text-xs text-slate-700 font-medium mt-1 leading-relaxed">
                    {selectedIncident.recommended_action}
                  </p>
                </div>
              </div>

              {/* Supervisor Action Logger */}
              <div className="pt-3 border-t border-slate-100 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-900 font-mono">
                    Supervisor Response Logging
                  </span>
                  {actionSuccess && (
                    <span className="text-[11px] text-emerald-600 font-bold flex items-center gap-1">
                      <CheckCircle className="w-3.5 h-3.5" /> Action Logged
                    </span>
                  )}
                </div>

                {/* 1-Click Quick Action Buttons */}
                <div className="flex flex-wrap gap-1.5">
                  <button
                    disabled={submittingAction}
                    onClick={() => handleQuickAction('Quarantine carton for structural inspection')}
                    className="text-[11px] font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded transition-colors"
                  >
                    Quarantine Carton
                  </button>
                  <button
                    disabled={submittingAction}
                    onClick={() => handleQuickAction('Enforce mandatory 2-person team lift')}
                    className="text-[11px] font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded transition-colors"
                  >
                    Enforce Team Lift
                  </button>
                  <button
                    disabled={submittingAction}
                    onClick={() => handleQuickAction('Logged operator coaching note')}
                    className="text-[11px] font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded transition-colors"
                  >
                    Log Coaching Note
                  </button>
                </div>

                {/* Custom Note Input */}
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="Enter custom supervisor intervention note..."
                    value={actionNote}
                    onChange={(e) => setActionNote(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleCustomActionSubmit();
                    }}
                    className="flex-1 text-xs px-3 py-1.5 rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500"
                  />
                  <button
                    disabled={!actionNote.trim() || submittingAction}
                    onClick={handleCustomActionSubmit}
                    className="px-3 py-1.5 rounded bg-sky-600 hover:bg-sky-700 text-white font-semibold text-xs disabled:opacity-50 transition-colors flex items-center gap-1"
                  >
                    <Send className="w-3 h-3" />
                    <span>Log</span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-16 text-center text-slate-400 space-y-2">
              <FileCheck className="w-10 h-10 mx-auto text-slate-300" />
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">NO INCIDENT SELECTED</h4>
              <p className="text-xs text-slate-500 max-w-xs mx-auto">
                Select an incident from the audit list on the left to inspect multi-frame evidence, 3-tier Responsible AI explanations, and record interventions.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
