import React from 'react';
import {
  Activity,
  AlertTriangle,
  Play,
  Pause,
  RefreshCw,
  Warehouse,
  Radio,
  Sliders,
  HelpCircle,
} from 'lucide-react';
import { RiskBadge } from '../ui/Badge';
import { VideoState } from '../../types/warehouse';

export const CareGuardBrandMark: React.FC<{ className?: string }> = ({ className = "w-6 h-6" }) => (
  <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
    {/* Geometric Protection Shield */}
    <path
      d="M16 3L27 7.5V15.5C27 22.5 22.2 27.8 16 29.5C9.8 27.8 5 22.5 5 15.5V7.5L16 3Z"
      fill="url(#shieldGrad)"
      stroke="url(#shieldStroke)"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
    {/* Warehouse Cube / Cargo Package Core */}
    <path
      d="M16 9.5L22 13V19L16 22.5L10 19V13L16 9.5Z"
      fill="#0c4a6e"
      fillOpacity="0.8"
      stroke="#38bdf8"
      strokeWidth="1.2"
      strokeLinejoin="round"
    />
    <path
      d="M16 9.5V22.5M10 13L16 16.5L22 13"
      stroke="#7dd3fc"
      strokeWidth="1.2"
      strokeLinejoin="round"
    />
    {/* Computer Vision Aperture Corner Crosshairs */}
    <path d="M12 11H10V13M20 11H22V13M10 18V20H12M22 18V20H20" stroke="#38bdf8" strokeWidth="1.2" strokeLinecap="round" />
    {/* Center Vision Focus Node */}
    <circle cx="16" cy="16" r="1.5" fill="#38bdf8" />
    <defs>
      <linearGradient id="shieldGrad" x1="16" y1="3" x2="16" y2="29.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0369a1" />
        <stop offset="100%" stopColor="#0f172a" />
      </linearGradient>
      <linearGradient id="shieldStroke" x1="5" y1="3" x2="27" y2="29.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#38bdf8" />
        <stop offset="100%" stopColor="#0284c7" />
      </linearGradient>
    </defs>
  </svg>
);

interface HeaderProps {
  videoState: VideoState | null;
  qualityScore: number;
  onRefresh: () => void;
  onTogglePlay: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  videoState,
  qualityScore,
  onRefresh,
  onTogglePlay,
}) => {
  const currentRisk = videoState?.current_risk_level || 'GREEN';

  return (
    <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-30 px-6 py-3 shadow-md">
      <div className="flex items-center justify-between">
        {/* Left: Product Identity & Core Tagline */}
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-lg bg-slate-950 flex items-center justify-center text-white shadow-sm shadow-sky-500/20 border border-sky-500/40">
            <CareGuardBrandMark className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-extrabold tracking-wider text-white font-mono flex items-center">
                <span>CareGuard</span><span className="text-sky-400 ml-1">AI</span>
              </h1>
              <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-sky-300 px-2 py-0.5 rounded border border-slate-700 font-mono">
                Warehouse Safety Intelligence
              </span>
            </div>
            <p className="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5 font-medium">
              <span className="text-slate-300">See Risk. Prevent Damage.</span>
              <span className="text-slate-600">•</span>
              <span className="text-slate-400 font-medium">Godrej Enterprises Group</span>
            </p>
          </div>
        </div>

        {/* Right: Operational Status, Active Monitoring Zone, & Telemetry */}
        <div className="flex items-center gap-4">
          {/* Active Monitoring Zone */}
          <div className="hidden lg:flex items-center gap-2 bg-slate-800/80 border border-slate-700/80 px-3 py-1.5 rounded-lg text-xs">
            <Warehouse className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-slate-400 text-[11px]">ACTIVE MONITORING ZONE:</span>
            <span className="font-mono font-bold text-white text-[11px]">BAY 01 • GENERAL STAGING</span>
          </div>

          {/* Handling Quality Index */}
          <div
            className="flex items-center gap-2.5 bg-slate-800/80 border border-slate-700/80 px-3 py-1.5 rounded-lg text-xs cursor-help group relative"
            title="Severity-weighted operational index based on recorded handling-risk events (100 baseline: RED=-10, ORANGE=-5, YELLOW=-2, GREEN=0)."
          >
            <div>
              <div className="text-[9px] uppercase font-bold text-slate-400 tracking-wider flex items-center gap-1">
                <span>HANDLING QUALITY INDEX</span>
                <HelpCircle className="w-2.5 h-2.5 text-slate-500" />
              </div>
              <div className="text-xs font-bold font-mono text-white flex items-center gap-1">
                <span className={qualityScore >= 85 ? 'text-emerald-400' : 'text-amber-400'}>{qualityScore}</span>
                <span className="text-[10px] font-normal text-slate-500">/ 100</span>
              </div>
            </div>
            <div className={`w-6 h-6 rounded flex items-center justify-center font-mono font-bold text-[11px] ${
              qualityScore >= 85 ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-amber-950 text-amber-300 border border-amber-800'
            }`}>
              {qualityScore >= 85 ? 'A' : (qualityScore >= 70 ? 'B' : 'C')}
            </div>
          </div>

          {/* Current Operational Status */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-400 font-medium hidden sm:inline">Status:</span>
            <RiskBadge level={videoState?.is_running ? currentRisk : 'GREEN'} size="md">
              {!videoState?.is_running ? 'SYSTEM READY' : (currentRisk === 'GREEN' ? 'SAFE' : (currentRisk === 'YELLOW' ? 'ATTENTION' : (currentRisk === 'ORANGE' ? 'HIGH RISK' : 'CRITICAL')))}
            </RiskBadge>
          </div>

          {/* Stream Control & Refresh */}
          <div className="flex items-center gap-2 border-l border-slate-800 pl-4">
            <button
              onClick={onTogglePlay}
              className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md transition-all ${
                videoState?.is_running
                  ? 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700'
                  : 'bg-sky-600 hover:bg-sky-500 text-white shadow-sm shadow-sky-600/30'
              }`}
            >
              {videoState?.is_running ? (
                <>
                  <Pause className="w-3.5 h-3.5 text-amber-400" />
                  <span>Pause Stream</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>Start Stream</span>
                </>
              )}
            </button>

            <button
              onClick={onRefresh}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-md transition-colors border border-transparent hover:border-slate-700"
              title="Refresh Telemetry"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

