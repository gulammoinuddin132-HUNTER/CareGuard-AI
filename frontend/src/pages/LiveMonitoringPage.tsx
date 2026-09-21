import React, { useState, useEffect } from 'react';
import {
  Play,
  Pause,
  Upload,
  RefreshCw,
  Eye,
  Sliders,
  Sparkles,
  Zap,
  Camera,
  Activity,
  Layers,
  ChevronRight,
  ShieldAlert,
  ShieldCheck,
  RotateCcw,
  Film,
  Monitor,
  CheckCircle2,
  FileSearch,
  Maximize2,
  Minimize2,
  X,
  AlertTriangle,
} from 'lucide-react';
import { Card } from '../components/ui/Card';
import { RiskBadge } from '../components/ui/Badge';
import { VideoState, WarehouseEvent } from '../types/warehouse';

interface LiveMonitoringPageProps {
  videoState: VideoState | null;
  onTogglePlay: () => void;
  onUploadVideo: (file: File) => Promise<void>;
  onTriggerSimulation: (presetId: number) => Promise<void>;
  onSelectSource: (sourceType: 'file' | 'camera' | 'synthetic', pathOrIdx?: string | number) => Promise<void>;
}

type OverlayMode = 'clean' | 'detection' | 'tracking' | 'diagnostics';

export const LiveMonitoringPage: React.FC<LiveMonitoringPageProps> = ({
  videoState,
  onTogglePlay,
  onUploadVideo,
  onTriggerSimulation,
  onSelectSource,
}) => {
  const [selectedPreset, setSelectedPreset] = useState<number>(1);
  const [triggeringPresetId, setTriggeringPresetId] = useState<number | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [availableVideos, setAvailableVideos] = useState<Array<{ filename: string; path: string; size_mb: number }>>([]);
  const [feedKey, setFeedKey] = useState<number>(Date.now());
  const [overlayMode, setOverlayMode] = useState<OverlayMode>('clean');
  const [showEvidenceModal, setShowEvidenceModal] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [fullscreenError, setFullscreenError] = useState<string | null>(null);
  const [showSourceModal, setShowSourceModal] = useState<boolean>(false);
  const videoContainerRef = React.useRef<HTMLDivElement>(null);

  // Synchronize fullscreen state with browser API (handles ESC key correctly)
  useEffect(() => {
    const handleFullscreenChange = () => {
      const active = Boolean(document.fullscreenElement && document.fullscreenElement === videoContainerRef.current);
      setIsFullscreen(active);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const toggleFullscreen = async () => {
    if (!videoContainerRef.current) return;
    try {
      if (!document.fullscreenElement) {
        await videoContainerRef.current.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch {
      setFullscreenError("Fullscreen unavailable");
      setTimeout(() => setFullscreenError(null), 3000);
    }
  };

  const handleStartStreamClick = () => {
    if (videoState?.is_running) {
      onTogglePlay();
      setFeedKey(Date.now());
      return;
    }
    const hasSelectedSource = Boolean(
      videoState?.video_file ||
      (videoState?.active_source && videoState.active_source !== 'STANDBY' && videoState.active_source !== 'INITIALIZING')
    );
    if (hasSelectedSource) {
      onTogglePlay();
      setFeedKey(Date.now());
    } else {
      setShowSourceModal(true);
    }
  };

  const currentEvent = videoState?.current_event;

  const getEvidenceUrl = (path?: string | null) => {
    if (!path) return null;
    if (path.startsWith('/api/evidence/')) return path;
    const fname = path.split(/[/\\]/).pop();
    return fname ? `/api/evidence/${fname}` : null;
  };

  useEffect(() => {
    import('../services/api').then(({ api }) => {
      api.listAvailableVideos().then(setAvailableVideos).catch(() => {});
    });
  }, [uploading]);

  const presets = [
    { id: 1, name: '1. Product Dropped', risk: 'RED', desc: 'Free-fall descent & floor impact' },
    { id: 2, name: '2. Product Dragged', risk: 'ORANGE', desc: 'Translating along floor plane' },
    { id: 3, name: '3. Rough Handling / Impact', risk: 'ORANGE', desc: 'Abrupt deceleration spike' },
    { id: 4, name: '4. Incorrect Stacking (Heavy on Light)', risk: 'ORANGE', desc: 'Inverted weight hierarchy' },
    { id: 5, name: '5. Unstable Stacking (Tilt)', risk: 'ORANGE', desc: 'Center-of-mass angular lean' },
    { id: 6, name: '6. Walkway Obstruction', risk: 'ORANGE', desc: 'Package dwell in safety lane' },
    { id: 7, name: '7. Heavy Manual Carry (No Trolley)', risk: 'YELLOW', desc: 'Single-person ergonomic strain' },
    { id: 8, name: '8. Pallet Misaligned', risk: 'YELLOW', desc: 'Overhanging cargo edge' },
    { id: 9, name: '9. Material Thrown / Tossed', risk: 'RED', desc: 'Parabolic aerial flight' },
    { id: 10, name: '10. Unsafe Unloading Order', risk: 'RED', desc: 'Bottom-pull instability' },
  ];

  const handleTrigger = async (presetId: number) => {
    setTriggeringPresetId(presetId);
    try {
      await onTriggerSimulation(presetId);
    } finally {
      setTriggeringPresetId(null);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploading(true);
      setUploadError(null);
      try {
        await onUploadVideo(file);
        setFeedKey(Date.now());
      } catch (err: any) {
        setUploadError(err.message || 'Upload failed');
      } finally {
        setUploading(false);
        e.target.value = '';
      }
    }
  };

  const handleSourceChange = async (type: 'file' | 'camera' | 'synthetic', val?: string | number) => {
    await onSelectSource(type, val);
    setFeedKey(Date.now());
  };

  const [inspectorTab, setInspectorTab] = useState<'event' | 'diagnostics'>('event');

  // Auto-switch to diagnostics tab when diagnostics mode selected
  useEffect(() => {
    if (overlayMode === 'diagnostics') {
      setInspectorTab('diagnostics');
    }
  }, [overlayMode]);

  const telemetry = videoState?.telemetry;

  return (
    <div className="space-y-6 animate-fade-in text-slate-800">
      {/* 1. Main Video Ingestion & Current Event / Diagnostics Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Left 7-cols: Dominant Video Viewport & Professional Controls */}
        <div className="xl:col-span-7 space-y-4">
          <div
            ref={videoContainerRef}
            className={`bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-lg relative flex items-center justify-center transition-all ${
              isFullscreen
                ? 'fixed inset-0 z-50 w-screen h-screen rounded-none border-none'
                : 'aspect-video'
            }`}
          >
            {uploading ? (
              <div className="flex flex-col items-center justify-center text-slate-400 gap-3">
                <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                <span className="text-xs font-mono tracking-wide text-emerald-400 font-semibold">
                  INGESTING VIDEO CLIP & INITIALIZING PIPELINE...
                </span>
              </div>
            ) : (
              <img
                key={`${feedKey}-${overlayMode}`}
                src={`/api/video/feed?overlay=${overlayMode}&t=${feedKey}`}
                alt="CareGuard AI Perception Feed"
                className="w-full h-full object-contain bg-black"
                onError={() => {
                  setTimeout(() => setFeedKey(Date.now()), 1500);
                }}
              />
            )}

            {/* Top-left Indicator Overlay */}
            <div className="absolute top-3 left-3 bg-slate-900/80 backdrop-blur-sm border border-slate-700/70 rounded-md px-2.5 py-1 text-white text-xs flex items-center gap-2 shadow-sm font-mono z-10">
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${videoState?.is_running ? 'bg-emerald-400 animate-pulse' : 'bg-slate-400'}`} />
                <span className="font-semibold text-white tracking-wide text-[11px]">
                  {videoState?.source_type === 'camera' ? 'LIVE' : (videoState?.is_running ? 'RECORDED' : 'STANDBY')}
                </span>
              </div>
              <span className="text-slate-600">•</span>
              <span className="text-slate-300 text-[10px]">
                {videoState?.video_file ? `BAY • ${videoState.video_file}` : 'BAY 01 • STAGING DOCK'}
              </span>
              {videoState?.is_running && overlayMode !== 'clean' && (
                <>
                  <span className="text-slate-600">|</span>
                  <span className="text-slate-300 text-[10px]">{videoState?.fps || 0} FPS</span>
                  <span className="text-sky-300 text-[10px]">{videoState?.detection_fps || 0} Det/s</span>
                </>
              )}
            </div>

            {/* Active Event Alert Banner (Top-Center) */}
            {currentEvent && currentEvent.risk_level && currentEvent.risk_level !== 'GREEN' && (
              <div className="absolute top-3 left-1/2 -translate-x-1/2 bg-slate-900/90 border border-slate-700 px-3 py-1 rounded-md text-white flex items-center gap-2 shadow-lg backdrop-blur-sm z-10 font-mono">
                <span className={`w-2 h-2 rounded-full animate-ping ${
                  currentEvent.risk_level === 'RED' ? 'bg-rose-500' : (currentEvent.risk_level === 'ORANGE' ? 'bg-amber-500' : 'bg-yellow-400')
                }`} />
                <span className={`text-[11px] font-bold ${
                  currentEvent.risk_level === 'RED' ? 'text-rose-400' : (currentEvent.risk_level === 'ORANGE' ? 'text-amber-400' : 'text-yellow-300')
                }`}>
                  {currentEvent.risk_level === 'RED' ? 'CRITICAL RISK' : (currentEvent.risk_level === 'ORANGE' ? 'HIGH RISK' : 'ATTENTION')}:
                </span>
                <span className="text-[11px] font-semibold text-slate-200">
                  {currentEvent.behaviour_type.replace(/_/g, ' ')}
                </span>
              </div>
            )}

            {/* Top-right Risk Badge & Fullscreen Toggle */}
            <div className="absolute top-3 right-3 flex items-center gap-2 z-10">
              <RiskBadge level={videoState?.is_running ? (videoState?.current_risk_level || 'GREEN') : 'GREEN'} size="sm">
                {!videoState?.is_running ? 'SYSTEM READY' : (videoState?.current_risk_level || 'SAFE')}
              </RiskBadge>
              <button
                onClick={toggleFullscreen}
                className="p-1.5 bg-slate-900/80 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white rounded-md text-xs flex items-center gap-1 font-semibold transition-colors"
                title={isFullscreen ? "Exit Full Screen (ESC)" : "Full Screen"}
              >
                {isFullscreen ? <Minimize2 className="w-3.5 h-3.5 text-sky-400" /> : <Maximize2 className="w-3.5 h-3.5 text-slate-300" />}
                <span className="hidden sm:inline text-[10px]">{isFullscreen ? 'Exit Full Screen' : 'Full Screen'}</span>
              </button>
            </div>

            {/* Fullscreen Unavailable Toast */}
            {fullscreenError && (
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-amber-950/90 border border-amber-600 px-3 py-1 rounded text-xs font-semibold text-amber-200 shadow-md z-10">
                {fullscreenError}
              </div>
            )}
          </div>

          {/* Video Control Bar & Analysis Overlay Selector */}
          <div className="bg-white rounded-lg border border-slate-200 p-3 flex flex-wrap items-center justify-between gap-3 shadow-xs">
            <div className="flex items-center gap-2">
              <button
                onClick={handleStartStreamClick}
                className={`flex items-center gap-1.5 text-xs font-semibold px-3.5 py-1.5 rounded-md transition-colors ${
                  videoState?.is_running
                    ? 'bg-slate-100 hover:bg-slate-200 text-slate-800'
                    : 'bg-sky-600 hover:bg-sky-700 text-white shadow-xs'
                }`}
              >
                {videoState?.is_running ? (
                  <>
                    <Pause className="w-3.5 h-3.5" /> Pause Feed
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5" /> Start Stream
                  </>
                )}
              </button>

              <label className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md border cursor-pointer transition-colors ${
                uploading
                  ? 'bg-emerald-100 text-emerald-800 border-emerald-300 animate-pulse pointer-events-none'
                  : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border-emerald-200'
              }`}>
                <Upload className="w-3.5 h-3.5" />
                <span>{uploading ? 'Uploading...' : 'Upload Clip'}</span>
                <input type="file" accept="video/mp4,video/avi,video/mkv,video/mov" className="hidden" disabled={uploading} onChange={handleFileUpload} />
              </label>

              {uploadError && (
                <div className="flex items-center gap-1 text-[11px] font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-1 rounded">
                  <span>{uploadError}</span>
                  <button onClick={() => setUploadError(null)} className="ml-1 text-rose-400 hover:text-rose-800 font-bold">✕</button>
                </div>
              )}

              <button
                onClick={() => handleSourceChange('camera', 0)}
                className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-md bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 transition-colors"
                title="Switch to Webcam"
              >
                <Camera className="w-3.5 h-3.5 text-slate-500" />
                <span>Webcam</span>
              </button>

              <button
                type="button"
                data-testid="fullscreen-btn"
                onClick={toggleFullscreen}
                className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-300 transition-colors cursor-pointer flex-shrink-0 shadow-xs"
                title={isFullscreen ? "Exit Full Screen (ESC)" : "Full Screen"}
              >
                {isFullscreen ? (
                  <Minimize2 className="w-3.5 h-3.5 text-sky-600" />
                ) : (
                  <Maximize2 className="w-3.5 h-3.5 text-slate-700" />
                )}
                <span className="font-semibold">{isFullscreen ? 'Exit Full Screen' : 'Full Screen'}</span>
              </button>
            </div>

            {/* Analysis Overlay Selector */}
            <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-md border border-slate-200 text-xs">
              <span className="text-[10px] font-bold text-slate-500 px-1.5 uppercase font-mono">Overlay:</span>
              {(['clean', 'detection', 'tracking', 'diagnostics'] as OverlayMode[]).map((mode) => (
                <button
                  key={mode}
                  onClick={() => {
                    setOverlayMode(mode);
                    import('../services/api').then(({ api }) => {
                      api.setOverlayMode(mode).catch(() => {});
                    });
                  }}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium transition-all ${
                    overlayMode === mode
                      ? 'bg-white text-slate-900 shadow-xs font-bold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {mode === 'clean' ? 'Clean View' : (mode === 'detection' ? 'Detection' : (mode === 'tracking' ? 'Tracking' : 'Full Diagnostics'))}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right 5-cols: CURRENT SAFETY EVENT & FULL DIAGNOSTICS INSPECTOR */}
        <div className="xl:col-span-5 space-y-4">
          <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-xs flex flex-col justify-between h-full min-h-[460px]">
            <div>
              {/* Tab Header for Event vs Diagnostics */}
              <div className="flex items-center justify-between mb-3.5 pb-2 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setInspectorTab('event')}
                    className={`text-xs font-bold uppercase tracking-wider font-mono px-2 py-1 rounded transition-colors ${
                      inspectorTab === 'event'
                        ? 'bg-slate-900 text-white'
                        : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    SAFETY EVENT
                  </button>
                  <button
                    onClick={() => setInspectorTab('diagnostics')}
                    className={`text-xs font-bold uppercase tracking-wider font-mono px-2 py-1 rounded transition-colors flex items-center gap-1.5 ${
                      inspectorTab === 'diagnostics'
                        ? 'bg-sky-700 text-white'
                        : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <Activity className="w-3 h-3" />
                    <span>DIAGNOSTICS</span>
                  </button>
                </div>

                {inspectorTab === 'event' && currentEvent && (
                  <div className="flex items-center gap-1.5">
                    {currentEvent.state === 'RESOLVED' && (
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded font-mono uppercase bg-slate-100 text-slate-700 border border-slate-300">
                        RESOLVED (AUDIT)
                      </span>
                    )}
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded font-mono uppercase ${
                      currentEvent.is_simulated
                        ? 'bg-amber-50 text-amber-800 border border-amber-200'
                        : 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                    }`}>
                      {currentEvent.is_simulated ? 'SIMULATED' : 'REAL CV DETECTED'}
                    </span>
                  </div>
                )}
                {inspectorTab === 'diagnostics' && (
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded font-mono uppercase bg-sky-50 text-sky-800 border border-sky-200">
                    REAL-TIME TELEMETRY
                  </span>
                )}
              </div>

              {/* TAB 1: SAFETY EVENT VIEW */}
              {inspectorTab === 'event' && (
                <>
                  {currentEvent ? (
                    <div className="space-y-3 animate-fade-in">
                      {/* Live Provenance Header */}
                      <div className="p-2.5 rounded-lg bg-slate-900 text-slate-200 border border-slate-800 font-mono text-[10px] space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${
                            currentEvent.is_simulated || (currentEvent.event_id && currentEvent.event_id.startsWith('SIM-'))
                              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                              : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          }`}>
                            {currentEvent.is_simulated || (currentEvent.event_id && currentEvent.event_id.startsWith('SIM-'))
                              ? 'SIMULATED SCENARIO'
                              : 'REAL CV DETECTED'}
                          </span>
                          <span className="text-slate-400 text-[9px]">
                            EVIDENCE: <b className={currentEvent.evidence_frame_path ? 'text-emerald-400' : 'text-amber-400'}>
                              {currentEvent.evidence_frame_path ? 'AVAILABLE' : 'PENDING'}
                            </b>
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-slate-400 text-[9px] pt-1 border-t border-slate-800">
                          <div>Source: <span className="text-slate-200 font-semibold truncate block">{currentEvent.video_source || telemetry?.video?.source || 'LIVE'}</span></div>
                          <div>Timestamp: <span className="text-slate-200 font-semibold">{currentEvent.start_timestamp ? currentEvent.start_timestamp.split(' ')[1] : 'N/A'}</span></div>
                          <div>Handler: <span className="text-sky-300 font-semibold">{currentEvent.person_track_id ? `Track #${currentEvent.person_track_id}` : 'UNASSOCIATED'}</span></div>
                          <div>Product: <span className="text-amber-300 font-semibold">{currentEvent.product_track_id ? `Track #${currentEvent.product_track_id}` : 'N/A'}</span></div>
                          <div className="col-span-2 pt-1 flex items-center justify-between text-[9px]">
                            <span className="text-slate-300">
                              Det Conf: <b className="text-sky-300">{currentEvent.detection_confidence ? `${Math.round(currentEvent.detection_confidence * 100)}%` : `${Math.round(currentEvent.confidence * 100)}%`}</b>
                            </span>
                            <span className="text-slate-300">
                              Beh Evidence: <b className="text-emerald-300">{currentEvent.behaviour_confidence ? `${Math.round(currentEvent.behaviour_confidence * 100)}%` : `${Math.round(currentEvent.confidence * 100)}%`}</b>
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Event Header & Risk */}
                      <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex items-start justify-between">
                        <div>
                          <span className="text-[10px] font-mono text-slate-400 block">{currentEvent.event_id}</span>
                          <h4 className="text-xs font-bold text-slate-900 mt-0.5">{currentEvent.behaviour_type}</h4>
                          <span className="text-[11px] text-slate-500 font-mono">{currentEvent.loading_bay || 'Bay 01'} • {currentEvent.start_timestamp ? currentEvent.start_timestamp.split(' ')[1] : ''}</span>
                        </div>
                        <RiskBadge level={currentEvent.risk_level} size="md">
                          {currentEvent.risk_level}
                        </RiskBadge>
                      </div>

                      {/* Deterministic Risk Policy Grounding */}
                      <div className={`p-2.5 rounded-lg border font-mono text-[10px] space-y-1.5 ${
                        currentEvent.risk_level === 'RED'
                          ? 'bg-rose-950/80 border-rose-800 text-rose-200'
                          : currentEvent.risk_level === 'ORANGE'
                          ? 'bg-amber-950/70 border-amber-800 text-amber-200'
                          : currentEvent.risk_level === 'YELLOW'
                          ? 'bg-yellow-950/70 border-yellow-800 text-yellow-200'
                          : 'bg-emerald-950/70 border-emerald-800 text-emerald-200'
                      }`}>
                        <div className="flex items-center justify-between">
                          <span className="font-bold uppercase tracking-wider text-[9px] flex items-center gap-1.5">
                            <span className={`w-2 h-2 rounded-full ${
                              currentEvent.risk_level === 'RED'
                                ? 'bg-rose-500 animate-ping'
                                : currentEvent.risk_level === 'ORANGE'
                                ? 'bg-amber-500'
                                : currentEvent.risk_level === 'YELLOW'
                                ? 'bg-yellow-400'
                                : 'bg-emerald-500'
                            }`} />
                            <span>POLICY GROUNDING • WHY {currentEvent.risk_level}?</span>
                          </span>
                          <span className="text-[9px] opacity-75">
                            {currentEvent.risk_level === 'RED' ? 'CRITICAL DAMAGE / SAFETY' : (currentEvent.risk_level === 'ORANGE' ? 'HIGH DAMAGE RISK' : (currentEvent.risk_level === 'YELLOW' ? 'ATTENTION REQUIRED' : 'NORMAL HANDLING'))}
                          </span>
                        </div>
                        <p className="text-[11px] leading-relaxed font-sans font-medium text-slate-100">
                          {currentEvent.severity_reason || (
                            currentEvent.risk_level === 'RED'
                              ? 'Event exceeded critical safety kinematics threshold, triggering urgent intervention policy.'
                              : currentEvent.risk_level === 'ORANGE'
                              ? 'Event exceeded operational risk parameters, requiring supervisor review.'
                              : 'Event detected non-standard handling practice.'
                          )}
                        </p>
                        {currentEvent.severity_factors && (
                          <div className="grid grid-cols-2 gap-1 pt-1 border-t border-white/10 text-[9px]">
                            {currentEvent.severity_factors.primary_metric && (
                              <div>Metric: <b className="text-white">{currentEvent.severity_factors.primary_metric}</b></div>
                            )}
                            {currentEvent.severity_factors.measured_value !== undefined && (
                              <div>Measured: <b className="text-white">{currentEvent.severity_factors.measured_value} {currentEvent.severity_factors.unit || ''}</b> (Thresh: {currentEvent.severity_factors.threshold})</div>
                            )}
                          </div>
                        )}
                      </div>

                      {/* 3-Tier Operational Breakdown */}
                      <div className="p-3 rounded-lg bg-sky-50/70 border border-sky-200">
                        <div className="flex items-center gap-1.5 text-xs font-bold text-sky-900">
                          <span className="w-4 h-4 rounded bg-sky-200 text-sky-800 flex items-center justify-center text-[10px] font-mono font-bold">1</span>
                          <span>What Happened</span>
                        </div>
                        <p className="text-xs sm:text-sm text-slate-800 mt-1 leading-relaxed font-semibold">
                          {currentEvent.observed_behaviour}
                        </p>
                      </div>

                      <div className="p-3 rounded-lg bg-amber-50/70 border border-amber-200">
                        <div className="flex items-center gap-1.5 text-xs font-bold text-amber-900">
                          <span className="w-4 h-4 rounded bg-amber-200 text-amber-800 flex items-center justify-center text-[10px] font-mono font-bold">2</span>
                          <span>Why It Matters</span>
                        </div>
                        <p className="text-xs sm:text-sm text-slate-800 mt-1 leading-relaxed font-semibold">
                          {currentEvent.potential_risk}
                        </p>
                      </div>

                      <div className="p-3 rounded-lg bg-emerald-50/70 border border-emerald-200">
                        <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-900">
                          <span className="w-4 h-4 rounded bg-emerald-200 text-emerald-800 flex items-center justify-center text-[10px] font-mono font-bold">3</span>
                          <span>What To Do</span>
                        </div>
                        <p className="text-xs sm:text-sm text-slate-800 mt-1 leading-relaxed font-semibold">
                          {currentEvent.recommended_action}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="py-12 text-center text-slate-400 space-y-2">
                      <ShieldCheck className="w-10 h-10 mx-auto text-emerald-500" />
                      <h4 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Normal Safe Handling</h4>
                      <p className="text-xs text-slate-500 font-medium">No unsafe handling events detected. Material movements are operating within safe parameters.</p>
                    </div>
                  )}
                </>
              )}

              {/* TAB 2: FULL DIAGNOSTICS INSPECTOR (5A - 5I Telemetry) */}
              {inspectorTab === 'diagnostics' && (
                <div className="space-y-3 animate-fade-in text-xs max-h-[460px] overflow-y-auto pr-1">
                  {/* 5A: Model Architecture */}
                  <div className="p-2.5 rounded-lg bg-slate-900 text-slate-200 border border-slate-800 font-mono">
                    <div className="flex items-center justify-between text-[11px] text-sky-400 font-bold mb-1.5">
                      <span>5A • MODEL ARCHITECTURE</span>
                      <span className="text-[10px] px-1.5 py-0.2 bg-emerald-500/20 text-emerald-400 rounded">
                        {telemetry?.model?.backend || 'PyTorch'}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[10px] text-slate-300">
                      <div>Model: <span className="text-white font-bold">{telemetry?.model?.name || 'YOLO26n Warehouse'}</span></div>
                      <div>Input: <span className="text-white font-bold">{telemetry?.model?.input_resolution || '640x640'}</span></div>
                      <div>Conf Thresh: <span className="text-white font-bold">{telemetry?.model?.conf_threshold ?? 0.25}</span></div>
                      <div>NMS Thresh: <span className="text-white font-bold">{telemetry?.model?.nms_threshold ?? 0.45}</span></div>
                      <div className="col-span-2 text-[9px] text-slate-400 truncate">
                        Path: {telemetry?.model?.model_path || 'data/models/yolo26n_warehouse.pt'}
                      </div>
                      <div className="col-span-2 text-[9px] text-sky-300">
                        Classes: {telemetry?.model?.classes?.join(', ') || 'person, product, pallet, mhe'}
                      </div>
                    </div>
                  </div>

                  {/* 5B: Video Ingestion & Performance */}
                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 font-mono text-[10px]">
                    <div className="flex items-center justify-between text-slate-800 font-bold mb-1.5">
                      <span className="text-sky-800">5B • VIDEO INGESTION & FPS</span>
                      <span className="text-slate-500">{telemetry?.video?.video_time || '00:00.0'}</span>
                    </div>
                    <div className="grid grid-cols-3 gap-1.5 text-slate-600">
                      <div className="bg-white p-1.5 rounded border border-slate-200">
                        <span className="text-slate-400 block text-[9px]">SOURCE</span>
                        <span className="font-bold text-slate-800 truncate block">{telemetry?.video?.source || 'N/A'}</span>
                      </div>
                      <div className="bg-white p-1.5 rounded border border-slate-200">
                        <span className="text-slate-400 block text-[9px]">FRAME</span>
                        <span className="font-bold text-slate-800">{telemetry?.video?.current_frame || 0} / {telemetry?.video?.total_frames || 'LIVE'}</span>
                      </div>
                      <div className="bg-white p-1.5 rounded border border-slate-200">
                        <span className="text-slate-400 block text-[9px]">DET FPS</span>
                        <span className="font-bold text-sky-600">{telemetry?.video?.detection_fps || 0} fps</span>
                      </div>
                      <div className="bg-white p-1.5 rounded border border-slate-200">
                        <span className="text-slate-400 block text-[9px]">INF LATENCY</span>
                        <span className="font-bold text-slate-800">{telemetry?.video?.inference_latency_ms || 0} ms</span>
                      </div>
                      <div className="bg-white p-1.5 rounded border border-slate-200">
                        <span className="text-slate-400 block text-[9px]">TRK LATENCY</span>
                        <span className="font-bold text-slate-800">{telemetry?.video?.tracking_latency_ms || 0} ms</span>
                      </div>
                      <div className="bg-white p-1.5 rounded border border-slate-200">
                        <span className="text-slate-400 block text-[9px]">RENDER FPS</span>
                        <span className="font-bold text-slate-800">{telemetry?.video?.render_fps || 0} fps</span>
                      </div>
                    </div>
                  </div>

                  {/* 5C & 5D: Active Warehouse Detections & Tracks */}
                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 font-mono text-[10px]">
                    <div className="flex items-center justify-between text-slate-800 font-bold mb-1.5">
                      <span className="text-emerald-800">5C/5D • DETECTIONS & TRACKS</span>
                      <span className="text-emerald-600 font-bold">{telemetry?.detection?.total_active || 0} ACTIVE</span>
                    </div>
                    {/* Category Count Badges */}
                    <div className="grid grid-cols-4 gap-1 text-center mb-2">
                      <div className="p-1 rounded bg-sky-50 border border-sky-200 text-sky-800">
                        <div className="text-[8px] text-sky-600">PERSON</div>
                        <div className="font-bold text-xs">{telemetry?.detection?.counts?.PERSON ?? 0}</div>
                      </div>
                      <div className="p-1 rounded bg-amber-50 border border-amber-200 text-amber-800">
                        <div className="text-[8px] text-amber-600">PRODUCT</div>
                        <div className="font-bold text-xs">{telemetry?.detection?.counts?.PRODUCT ?? 0}</div>
                      </div>
                      <div className="p-1 rounded bg-purple-50 border border-purple-200 text-purple-800">
                        <div className="text-[8px] text-purple-600">PALLET</div>
                        <div className="font-bold text-xs">{telemetry?.detection?.counts?.PALLET ?? 0}</div>
                      </div>
                      <div className="p-1 rounded bg-slate-100 border border-slate-300 text-slate-800">
                        <div className="text-[8px] text-slate-600">MHE</div>
                        <div className="font-bold text-xs">{telemetry?.detection?.counts?.MHE ?? 0}</div>
                      </div>
                    </div>

                    {/* Detections List */}
                    {telemetry?.detection?.detections && telemetry.detection.detections.length > 0 ? (
                      <div className="space-y-1">
                        {telemetry.detection.detections.map((d, i) => (
                          <div key={i} className="flex items-center justify-between p-1 bg-white rounded border border-slate-200 text-[9px]">
                            <span className="font-bold text-slate-800">{d.display_label}</span>
                            <span className="text-slate-500">Track #{d.track_id}</span>
                            <span className="text-slate-400 font-mono">[{d.bbox.map(n => Math.round(n)).join(',')}]</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-2 text-slate-400 italic text-[9px]">
                        NO ACTIVE WAREHOUSE DETECTIONS
                      </div>
                    )}
                  </div>

                  {/* 5E & 5F: Interaction Relationship & Kinematics */}
                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 font-mono text-[10px]">
                    <div className="flex items-center justify-between text-slate-800 font-bold mb-1.5">
                      <span className="text-purple-800">5E/5F • KINEMATICS & INTERACTION</span>
                      <span className="text-purple-700 font-bold">
                        {telemetry?.relationship?.interaction_state || telemetry?.relationship?.relationship || 'FREE'}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-1.5 text-slate-600">
                      <div className="bg-white p-1.5 rounded border border-slate-200">
                        <span className="text-slate-400 block text-[9px]">INTERACTION DIST</span>
                        <span className="font-bold text-slate-800">
                          {telemetry?.relationship?.edge_distance_px != null ? `${Math.round(telemetry.relationship.edge_distance_px)}px (edge)` : 'N/A'}
                        </span>
                      </div>
                      <div className="bg-white p-1.5 rounded border border-slate-200">
                        <span className="text-slate-400 block text-[9px]">VELOCITY (Vx, Vy)</span>
                        <span className="font-bold text-slate-800">
                          ({telemetry?.kinematics?.vx || 0}, {telemetry?.kinematics?.vy || 0}) px/s
                        </span>
                      </div>
                      <div className="bg-white p-1.5 rounded border border-slate-200">
                        <span className="text-slate-400 block text-[9px]">SPEED</span>
                        <span className="font-bold text-sky-600">{telemetry?.kinematics?.speed || 0} px/s</span>
                      </div>
                      <div className="bg-white p-1.5 rounded border border-slate-200">
                        <span className="text-slate-400 block text-[9px]">GROUND STATE</span>
                        <span className={`font-bold ${telemetry?.kinematics?.ground_state === 'AIRBORNE' ? 'text-rose-600' : 'text-emerald-600'}`}>
                          {telemetry?.kinematics?.ground_state || 'GROUNDED'} (el: {telemetry?.kinematics?.elevation_ratio || 0})
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 5G: Behaviour Engine Rule Evaluation */}
                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 font-mono text-[10px]">
                    <div className="flex items-center justify-between text-slate-800 font-bold mb-1.5">
                      <span className="text-amber-800">5G • BEHAVIOUR ENGINE EVALUATION</span>
                      <span className={`font-bold ${telemetry?.behaviour?.trigger_status === 'TRIGGERED' ? 'text-rose-600' : 'text-slate-600'}`}>
                        {telemetry?.behaviour?.trigger_status || 'IDLE'}
                      </span>
                    </div>
                    <div className="text-[9px] text-slate-700 bg-white p-1.5 rounded border border-slate-200">
                      <div>Candidate: <span className="font-bold text-slate-900">{telemetry?.behaviour?.candidate || 'NONE'}</span></div>
                      {telemetry?.behaviour?.rules && Object.keys(telemetry.behaviour.rules).length > 0 && (
                        <div className="mt-1 space-y-0.5 text-slate-500">
                          {Object.entries(telemetry.behaviour.rules).map(([k, v]) => (
                            <div key={k} className="truncate">{k}: <span className="text-slate-800 font-semibold">{v}</span></div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 5H: Why This Event Fired (Forensic Kinematic Audit) */}
                  <div className="p-2.5 rounded-lg bg-slate-900 text-slate-200 border border-slate-800 font-mono text-[10px]">
                    <div className="flex items-center justify-between text-slate-200 font-bold mb-1.5">
                      <span className="text-rose-400 font-bold">5H • WHY THIS EVENT FIRED</span>
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                        telemetry?.why_this_event_fired ? 'bg-rose-500/20 text-rose-300' : 'bg-slate-800 text-slate-400'
                      }`}>
                        {telemetry?.why_this_event_fired ? telemetry.why_this_event_fired.behaviour : 'NO ACTIVE EVENT'}
                      </span>
                    </div>

                    {telemetry?.why_this_event_fired ? (
                      <div className="space-y-1.5 text-[9px]">
                        <div className="bg-slate-950 p-2 rounded border border-slate-800 space-y-1">
                          <div className="text-slate-400 text-[9px] font-bold uppercase tracking-wider text-sky-400">TRIGGER CONDITIONS (MET)</div>
                          {telemetry.why_this_event_fired.trigger_conditions && Object.entries(telemetry.why_this_event_fired.trigger_conditions).map(([k, v]) => (
                            <div key={k} className="flex items-center justify-between border-b border-slate-900 pb-0.5">
                              <span className="text-slate-400">{k}:</span>
                              <span className="text-emerald-400 font-semibold">{String(v)}</span>
                            </div>
                          ))}
                        </div>

                        <div className="grid grid-cols-2 gap-1.5 text-[9px]">
                          <div className="bg-slate-950 p-1.5 rounded border border-slate-800">
                            <span className="text-slate-500 block text-[8px]">HORIZONTAL MOTION</span>
                            <span className="font-bold text-sky-400">{telemetry.why_this_event_fired.horizontal_speed ?? 0} px/s</span>
                          </div>
                          <div className="bg-slate-950 p-1.5 rounded border border-slate-800">
                            <span className="text-slate-500 block text-[8px]">VERTICAL MOTION</span>
                            <span className="font-bold text-sky-400">{telemetry.why_this_event_fired.vertical_speed ?? 0} px/s</span>
                          </div>
                          <div className="bg-slate-950 p-1.5 rounded border border-slate-800">
                            <span className="text-slate-500 block text-[8px]">DISPLACEMENT</span>
                            <span className="font-bold text-amber-400">{telemetry.why_this_event_fired.displacement ?? 0} px</span>
                          </div>
                          <div className="bg-slate-950 p-1.5 rounded border border-slate-800">
                            <span className="text-slate-500 block text-[8px]">DURATION</span>
                            <span className="font-bold text-amber-400">{telemetry.why_this_event_fired.duration_seconds ?? 0}s</span>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-2 text-slate-500 italic text-[9px]">
                        No active safety event triggered on current frame.
                      </div>
                    )}
                  </div>
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
                    onClick={() => setShowEvidenceModal(true)}
                    className="text-xs font-semibold px-3 py-1.5 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-800 transition-colors flex items-center gap-1"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>View Evidence</span>
                  </button>
                  <button
                    onClick={() => setFeedKey(Date.now())}
                    className="text-xs font-semibold px-3 py-1.5 rounded-md bg-sky-600 hover:bg-sky-700 text-white transition-colors flex items-center gap-1"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Replay Event</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 2. 1-Click Interactive Behaviour Simulator Bar */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-3">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-xs uppercase tracking-wider text-slate-900 font-mono">
                1-Click Warehouse Scenario Simulator
              </h3>
              <span className="text-[9px] font-bold px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 uppercase tracking-wider font-mono">
                SIMULATED DATA
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Trigger any of the 10 target behaviours to demonstrate automated sequence detection and Responsible AI explainability.
            </p>
          </div>
          <span className="text-[10px] text-slate-400 font-mono">
            10 Standard Presets
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {presets.map((p) => {
            const isThisTriggering = triggeringPresetId === p.id;
            return (
              <button
                key={p.id}
                disabled={triggeringPresetId !== null}
                onClick={() => handleTrigger(p.id)}
                className={`p-2.5 rounded-lg border text-left transition-all group ${
                  isThisTriggering
                    ? 'border-amber-400 bg-amber-50/70 shadow-xs ring-1 ring-amber-400'
                    : 'border-slate-200 bg-slate-50/50 hover:bg-sky-50/40 hover:border-sky-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold font-mono text-slate-400 group-hover:text-sky-600">
                    {isThisTriggering ? 'Triggering...' : `#${p.id}`}
                  </span>
                  <span className={`w-1.5 h-1.5 rounded-full ${isThisTriggering ? 'bg-amber-500 animate-ping' : (p.risk === 'RED' ? 'bg-rose-500' : (p.risk === 'ORANGE' ? 'bg-orange-500' : 'bg-amber-500'))}`} />
                </div>
                <div className="text-xs font-semibold text-slate-800 mt-1 line-clamp-1 group-hover:text-sky-700">
                  {p.name.split('. ')[1]}
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5 line-clamp-1">
                  {p.desc}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Evidence Modal */}
      {showEvidenceModal && currentEvent && (
        <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xl max-w-2xl w-full p-5 space-y-4 animate-fade-in">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Incident Evidence Frame</h3>
                <span className="text-xs text-slate-500 font-mono">{currentEvent.event_id} • {currentEvent.behaviour_type}</span>
              </div>
              <button
                onClick={() => setShowEvidenceModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold p-1"
              >
                ✕
              </button>
            </div>
            <div className="bg-slate-900 rounded-lg overflow-hidden aspect-video flex items-center justify-center border border-slate-800 relative">
              {getEvidenceUrl(currentEvent.evidence_frame_path) ? (
                <img
                  src={getEvidenceUrl(currentEvent.evidence_frame_path)!}
                  alt="Event Evidence"
                  className="w-full h-full object-contain bg-black"
                  onError={(e) => {
                    const target = e.target as HTMLImageElement;
                    target.style.display = 'none';
                    const parent = target.parentElement;
                    if (parent && !parent.querySelector('.evidence-fallback')) {
                      const fallback = document.createElement('div');
                      fallback.className = 'evidence-fallback text-center p-6 text-slate-400 space-y-1';
                      fallback.innerHTML = '<div class="text-xs font-mono font-bold text-amber-400">EVIDENCE FRAME UNAVAILABLE</div><div class="text-[11px] text-slate-500">Evidence capture snapshot not yet written or pending buffer flush</div>';
                      parent.appendChild(fallback);
                    }
                  }}
                />
              ) : (
                <div className="text-center p-6 text-slate-400 space-y-1">
                  <div className="text-xs font-mono font-bold text-amber-400">EVIDENCE FRAME UNAVAILABLE</div>
                  <div className="text-[11px] text-slate-500">No snapshot recorded for this session event</div>
                </div>
              )}
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700 leading-relaxed font-medium">
              <b>Observed Behaviour:</b> {currentEvent.observed_behaviour}
            </div>
            <div className="flex justify-end">
              <button
                onClick={() => setShowEvidenceModal(false)}
                className="px-4 py-2 bg-slate-900 text-white rounded-md text-xs font-semibold hover:bg-slate-800"
              >
                Close Evidence
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Explicit Source Selection Modal */}
      {showSourceModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xl max-w-lg w-full p-6 space-y-5 animate-fade-in">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center">
                  <Play className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Select a Video Source</h3>
                  <p className="text-[11px] text-slate-500">Choose an ingestion feed to begin perception analysis</p>
                </div>
              </div>
              <button
                onClick={() => setShowSourceModal(false)}
                className="text-slate-400 hover:text-slate-700 p-1 rounded-md"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Webcam Option */}
              <button
                onClick={async () => {
                  setShowSourceModal(false);
                  await handleSourceChange('camera', 0);
                }}
                className="flex flex-col items-start p-4 rounded-lg border border-slate-200 hover:border-sky-500 hover:bg-sky-50/50 transition-all text-left group"
              >
                <div className="w-8 h-8 rounded-md bg-slate-100 group-hover:bg-sky-100 text-slate-700 group-hover:text-sky-600 flex items-center justify-center mb-2.5">
                  <Camera className="w-4 h-4" />
                </div>
                <div className="font-semibold text-xs text-slate-900">Physical Webcam</div>
                <div className="text-[11px] text-slate-500 mt-0.5">Live USB / camera sensor stream</div>
                <span className="mt-3 text-[10px] font-bold text-sky-600 group-hover:underline flex items-center gap-1">
                  Connect Webcam →
                </span>
              </button>

              {/* Recorded Video Option */}
              <button
                onClick={async () => {
                  setShowSourceModal(false);
                  if (availableVideos.length > 0) {
                    await handleSourceChange('file', availableVideos[0].path);
                  }
                }}
                className="flex flex-col items-start p-4 rounded-lg border border-slate-200 hover:border-emerald-500 hover:bg-emerald-50/50 transition-all text-left group"
              >
                <div className="w-8 h-8 rounded-md bg-slate-100 group-hover:bg-emerald-100 text-slate-700 group-hover:text-emerald-600 flex items-center justify-center mb-2.5">
                  <Film className="w-4 h-4" />
                </div>
                <div className="font-semibold text-xs text-slate-900">Recorded Warehouse Video</div>
                <div className="text-[11px] text-slate-500 mt-0.5">Play pre-recorded staging clips</div>
                <span className="mt-3 text-[10px] font-bold text-emerald-600 group-hover:underline flex items-center gap-1">
                  Load Warehouse Clip →
                </span>
              </button>
            </div>

            {/* Quick clips list if available */}
            {availableVideos.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-slate-100">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-mono">Available Warehouse Clips:</span>
                <div className="max-h-36 overflow-y-auto space-y-1 pr-1">
                  {availableVideos.map((v) => (
                    <button
                      key={v.path}
                      onClick={async () => {
                        setShowSourceModal(false);
                        await handleSourceChange('file', v.path);
                      }}
                      className="w-full text-left px-2.5 py-1.5 rounded text-xs text-slate-700 hover:bg-slate-100 flex items-center justify-between transition-colors border border-transparent hover:border-slate-200"
                    >
                      <span className="truncate max-w-[280px] font-medium">{v.filename}</span>
                      <span className="text-[10px] text-slate-400 font-mono">{v.size_mb} MB</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowSourceModal(false)}
                className="px-4 py-1.5 text-xs font-semibold text-slate-600 hover:text-slate-800 rounded-md"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
