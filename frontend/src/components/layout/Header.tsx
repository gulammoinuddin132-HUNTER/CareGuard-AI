import React, { useState } from 'react';
import {
  Warehouse,
  Play,
  Pause,
  RefreshCw,
  HelpCircle,
  Shield,
  Activity,
} from 'lucide-react';
import { RiskBadge } from '../ui/Badge';
import { VideoState } from '../../types/warehouse';
import careguardLogo from '../../assets/careguard-logo.png';

interface HeaderProps {
  videoState: VideoState | null;
  qualityScore?: number | null;
  onRefresh: () => void | Promise<void>;
  onTogglePlay: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  videoState,
  qualityScore,
  onRefresh,
  onTogglePlay,
}) => {
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const currentRisk = videoState?.current_risk_level || 'GREEN';
  const scoreVal = typeof qualityScore === 'number' ? qualityScore : 100;

  // Semantic Quality Label & Color
  const getQualityTier = (score: number) => {
    if (score >= 90) return { label: 'Optimal / Safe', color: 'text-emerald-400', badge: 'A' };
    if (score >= 75) return { label: 'Good / Watch', color: 'text-amber-400', badge: 'B' };
    if (score >= 50) return { label: 'Needs Attention', color: 'text-orange-400', badge: 'C' };
    return { label: 'Critical Action', color: 'text-rose-400', badge: 'D' };
  };

  const qualityInfo = getQualityTier(scoreVal);

  const handleRefreshClick = async () => {
    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setTimeout(() => setIsRefreshing(false), 500);
    }
  };

  return (
    <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-30 px-6 py-3 shadow-md text-slate-100">
      <div className="flex items-center justify-between">
        {/* Left: Official CareGuard AI Brand Mark & Mission */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <img
              src={careguardLogo}
              alt="CareGuard AI"
              className="h-10 w-10 object-contain rounded-lg bg-white/95 p-0.5 shadow-xs"
            />
            <div>
              <div className="flex items-center gap-2.5">
                <span className="text-xl font-extrabold tracking-tight text-white font-sans">
                  CareGuard<span className="text-sky-400 ml-0.5">AI</span>
                </span>
                <span className="text-xs font-bold uppercase tracking-wider bg-slate-800 text-sky-300 px-2.5 py-0.5 rounded-md border border-slate-700">
                  Warehouse Operations
                </span>
              </div>
              <p className="text-xs text-slate-300 font-semibold mt-0.5">
                Warehouse Safety & Damage Prevention
              </p>
            </div>
          </div>
        </div>

        {/* Right: Operational Status, Handling Quality, & Stream Controls */}
        <div className="flex items-center gap-4">
          {/* Active Monitoring Zone */}
          <div className="hidden xl:flex items-center gap-2 bg-slate-800/90 border border-slate-700 px-3.5 py-1.5 rounded-lg text-xs">
            <Warehouse className="w-4 h-4 text-sky-400" />
            <div className="flex flex-col">
              <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                Monitoring Zone
              </span>
              <span className="font-bold text-white text-xs">
                Bay 01 • Staging & Conveyor Dock
              </span>
            </div>
          </div>

          {/* Handling Quality Score Metric */}
          <div
            className="flex items-center gap-2.5 bg-slate-800/90 border border-slate-700 px-3.5 py-1.5 rounded-lg text-xs"
            title="Rolling Handling Quality score (0-100) based on recent handling events."
          >
            <div>
              <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                Handling Quality
              </div>
              <div className="text-sm font-extrabold font-mono text-white flex items-baseline gap-1 mt-0.5">
                <span className={qualityInfo.color}>{scoreVal}</span>
                <span className="text-xs font-medium text-slate-400">/ 100</span>
              </div>
            </div>
            <div
              className={`w-7 h-7 rounded-md flex items-center justify-center font-mono font-extrabold text-xs shadow-xs ${
                scoreVal >= 85
                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700'
                  : scoreVal >= 70
                  ? 'bg-amber-950/80 text-amber-300 border border-amber-700'
                  : 'bg-rose-950/80 text-rose-300 border border-rose-700'
              }`}
            >
              {qualityInfo.badge}
            </div>
          </div>

          {/* Current Operational Status */}
          <div className="flex items-center">
            <RiskBadge level={videoState?.is_running ? currentRisk : 'GREEN'} size="md">
              {!videoState?.is_running
                ? 'SYSTEM READY'
                : currentRisk === 'GREEN'
                ? 'SAFE'
                : currentRisk === 'YELLOW'
                ? 'ATTENTION'
                : currentRisk === 'ORANGE'
                ? 'HIGH RISK'
                : 'CRITICAL'}
            </RiskBadge>
          </div>

          {/* Stream Control & Refresh */}
          <div className="flex items-center gap-2 border-l border-slate-800 pl-3">
            <button
              onClick={onTogglePlay}
              className={`flex items-center gap-2 text-xs font-bold px-4 py-2 rounded-lg transition-all shadow-xs ${
                videoState?.is_running
                  ? 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700'
                  : 'bg-sky-600 hover:bg-sky-500 active:bg-sky-700 text-white shadow-sky-600/30'
              }`}
            >
              {videoState?.is_running ? (
                <>
                  <Pause className="w-4 h-4 text-amber-400" />
                  <span>Pause Stream</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  <span>Start Stream</span>
                </>
              )}
            </button>

            <button
              onClick={handleRefreshClick}
              disabled={isRefreshing}
              className="flex items-center gap-1.5 text-xs font-semibold px-3 py-2 text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors border border-slate-700 disabled:opacity-60"
              title="Refresh database telemetry and dashboard state"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-sky-400' : ''}`} />
              <span className="hidden md:inline">Refresh</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
