import React, { useState } from 'react';
import {
  Settings as SettingsIcon,
  Sliders,
  MapPin,
  Camera,
  Shield,
  Save,
  CheckCircle,
  Eye,
  SlidersHorizontal,
  Lock,
  Info,
  HelpCircle,
  AlertCircle,
} from 'lucide-react';

interface SettingsPageProps {
  onSaveSettings: (settings: any) => Promise<void>;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ onSaveSettings }) => {
  const [dropVelocity, setDropVelocity] = useState<number>(120);
  const [dragSpeed, setDragSpeed] = useState<number>(20);
  const [tiltOffset, setTiltOffset] = useState<number>(18);
  const [walkwayDwell, setWalkwayDwell] = useState<number>(2.5);
  const [heavyCargoArea, setHeavyCargoArea] = useState<number>(12000);
  const [throwVelocity, setThrowVelocity] = useState<number>(160);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  const handleSave = async () => {
    await onSaveSettings({
      drop_velocity_threshold: dropVelocity,
      drag_speed_threshold: dragSpeed,
      unstable_stack_tilt_px: tiltOffset,
      walkway_dwell_seconds: walkwayDwell,
      heavy_cargo_area_px: heavyCargoArea,
      throw_velocity_threshold: throwVelocity,
    });
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-5 animate-fade-in text-slate-800">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
              Detection & Kinematic Settings
            </h1>
            <span className="text-[10px] font-mono bg-sky-50 text-sky-700 border border-sky-200 px-2 py-0.5 rounded font-bold">
              PERCEPTION TUNING
            </span>
          </div>
          <p className="text-[11px] text-slate-500 mt-0.5">
            Configure how much motion or spatial change CareGuard requires before classifying an observation as meaningful.
          </p>
        </div>
        <button
          onClick={handleSave}
          className="flex items-center gap-1.5 text-xs font-semibold px-3.5 py-2 rounded-md bg-sky-600 hover:bg-sky-700 text-white shadow-xs transition-colors self-start sm:self-auto"
        >
          <Save className="w-3.5 h-3.5" />
          <span>Save Thresholds</span>
        </button>
      </div>

      {savedSuccess && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg flex items-center gap-2 font-medium">
          <CheckCircle className="w-4 h-4 text-emerald-600" />
          <span>Threshold configurations updated and committed to active CV pipeline.</span>
        </div>
      )}

      {/* Kinematics Concept Explanation Banner */}
      <div className="p-3.5 rounded-lg bg-sky-50/70 border border-sky-100 text-xs text-sky-950 flex items-start gap-2.5">
        <Info className="w-4 h-4 text-sky-700 shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <span className="font-bold text-sky-900">Understanding Kinematic Parameters: </span>
          Kinematics describes how objects move over time, including displacement, velocity, acceleration, direction and duration. CareGuard computes continuous trajectory vectors for tracked cargo items to distinguish safe handling from risk exposures.
        </div>
      </div>

      {/* 1. Kinematics Thresholds */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-xs">
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 font-mono">
              Kinematic Tolerance Sliders
            </h3>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Calibrated for 720p / 1080p industrial warehouse cameras
            </p>
          </div>
          <SlidersHorizontal className="w-4 h-4 text-slate-400" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Drop Velocity */}
          <div className="space-y-1.5 p-3 rounded-lg border border-slate-200 bg-slate-50/40">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-800">Drop Velocity Spike Threshold</span>
              <span className="font-mono font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-200 text-[11px]">
                {dropVelocity} px/s
              </span>
            </div>
            <input
              type="range"
              min="60"
              max="250"
              value={dropVelocity}
              onChange={(e) => setDropVelocity(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-sky-600"
            />
            <p className="text-[10px] text-slate-600 leading-snug">
              Triggers free-fall alert when downward package velocity vector exceeds this threshold.
            </p>
            <div className="text-[9px] font-mono text-slate-400 italic">
              * Configured detection threshold; camera calibration and scene geometry affect its interpretation.
            </div>
          </div>

          {/* Floor Dragging */}
          <div className="space-y-1.5 p-3 rounded-lg border border-slate-200 bg-slate-50/40">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-800">Floor Dragging Speed Threshold</span>
              <span className="font-mono font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-200 text-[11px]">
                {dragSpeed} px/s
              </span>
            </div>
            <input
              type="range"
              min="10"
              max="60"
              value={dragSpeed}
              onChange={(e) => setDragSpeed(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-sky-600"
            />
            <p className="text-[10px] text-slate-600 leading-snug">
              Horizontal translation along floor plane without vertical clearance or trolley support.
            </p>
            <div className="text-[9px] font-mono text-slate-400 italic">
              * Configured detection threshold; camera calibration and scene geometry affect its interpretation.
            </div>
          </div>

          {/* Stack Tilt */}
          <div className="space-y-1.5 p-3 rounded-lg border border-slate-200 bg-slate-50/40">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-800">Stack Tilt Offset Threshold</span>
              <span className="font-mono font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-200 text-[11px]">
                {tiltOffset} px
              </span>
            </div>
            <input
              type="range"
              min="10"
              max="40"
              value={tiltOffset}
              onChange={(e) => setTiltOffset(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-sky-600"
            />
            <p className="text-[10px] text-slate-600 leading-snug">
              Lateral displacement of center-of-mass between vertically stacked cargo boxes.
            </p>
            <div className="text-[9px] font-mono text-slate-400 italic">
              * Configured detection threshold; camera calibration and scene geometry affect its interpretation.
            </div>
          </div>

          {/* Walkway Dwell */}
          <div className="space-y-1.5 p-3 rounded-lg border border-slate-200 bg-slate-50/40">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-800">Walkway Stationary Dwell Limit</span>
              <span className="font-mono font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-200 text-[11px]">
                {walkwayDwell}s
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="10"
              step="0.5"
              value={walkwayDwell}
              onChange={(e) => setWalkwayDwell(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-sky-600"
            />
            <p className="text-[10px] text-slate-600 leading-snug">
              Duration a package can remain resting inside designated transit lanes before obstruction alert.
            </p>
            <div className="text-[9px] font-mono text-slate-400 italic">
              * Configured temporal threshold; evaluated continuously per tracked package ID.
            </div>
          </div>

          {/* Heavy Cargo Area */}
          <div className="space-y-1.5 p-3 rounded-lg border border-slate-200 bg-slate-50/40">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-800">Heavy Cargo BBox Area Threshold</span>
              <span className="font-mono font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-200 text-[11px]">
                {heavyCargoArea} px²
              </span>
            </div>
            <input
              type="range"
              min="6000"
              max="25000"
              step="500"
              value={heavyCargoArea}
              onChange={(e) => setHeavyCargoArea(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-sky-600"
            />
            <p className="text-[10px] text-slate-600 leading-snug">
              Minimum projected 2D image area to classify cargo as heavy manual lift risk when carried alone.
            </p>
            <div className="text-[9px] font-mono text-slate-400 italic">
              * Configured detection threshold; camera calibration and scene geometry affect its interpretation.
            </div>
          </div>

          {/* Throw Velocity */}
          <div className="space-y-1.5 p-3 rounded-lg border border-slate-200 bg-slate-50/40">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-800">Throw / Launch Velocity Threshold</span>
              <span className="font-mono font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-200 text-[11px]">
                {throwVelocity} px/s
              </span>
            </div>
            <input
              type="range"
              min="100"
              max="300"
              value={throwVelocity}
              onChange={(e) => setThrowVelocity(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-sky-600"
            />
            <p className="text-[10px] text-slate-600 leading-snug">
              Parabolic launch speed threshold indicating violent throwing or tossing of merchandise.
            </p>
            <div className="text-[9px] font-mono text-slate-400 italic">
              * Configured detection threshold; camera calibration and scene geometry affect its interpretation.
            </div>
          </div>
        </div>
      </div>

      {/* 2. Warehouse Spatial Geofence Zones */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-xs">
        <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-100">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 font-mono">
              Warehouse Spatial Geofence Zones
            </h3>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Zones define spatial operating context for behaviour rules
            </p>
          </div>
          <MapPin className="w-4 h-4 text-slate-400" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50/50">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900">General Staging Bay</span>
              <span className="text-[10px] bg-sky-50 text-sky-700 font-mono font-bold px-2 py-0.5 rounded border border-sky-200">
                BAY #1
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-1">Primary loading/unloading area for incoming pallets.</p>
          </div>

          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50/50">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900">Pedestrian Corridor</span>
              <span className="text-[10px] bg-amber-50 text-amber-700 font-mono font-bold px-2 py-0.5 rounded border border-amber-200">
                BAY #2
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-1">Zero-obstruction walkway and emergency egress route.</p>
          </div>

          <div className="p-3 rounded-lg border border-slate-200 bg-slate-50/50">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900">Heavy Racking Area</span>
              <span className="text-[10px] bg-indigo-50 text-indigo-700 font-mono font-bold px-2 py-0.5 rounded border border-indigo-200">
                BAY #3
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-1">Multi-tier pallet storage and vertical staging zone.</p>
          </div>
        </div>
      </div>

      {/* 3. Responsible AI & Worker Privacy Principles */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-xs">
        <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-100">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 font-mono">
              Responsible AI & Worker Privacy Principles
            </h3>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Built-in privacy-preserving operational video analytics guidelines
            </p>
          </div>
          <Lock className="w-4 h-4 text-slate-400" />
        </div>

        <div className="space-y-2 text-xs text-slate-600 leading-relaxed">
          <div className="p-2.5 rounded border border-slate-100 bg-slate-50/50">
            <span className="font-bold text-slate-800">1. Non-Punitive Ergonomic & Handling Focus:</span> CareGuard AI evaluates package kinematics and procedural handling workflows to prevent product damage and improve ergonomics. It does NOT track employee identity, attendance, or perform punitive scoring.
          </div>
          <div className="p-2.5 rounded border border-slate-100 bg-slate-50/50">
            <span className="font-bold text-slate-800">2. Zero Facial Recognition:</span> Identity scoring, employee facial matching, and biometric indexing are permanently excluded from CareGuard AI.
          </div>
          <div className="p-2.5 rounded border border-slate-100 bg-slate-50/50">
            <span className="font-bold text-slate-800">3. Audit Trail & Data Retention:</span> Incident evidence packages and kinematics metadata are retained for 30 days for operational audit and root cause analysis.
          </div>
        </div>
      </div>
    </div>
  );
};


