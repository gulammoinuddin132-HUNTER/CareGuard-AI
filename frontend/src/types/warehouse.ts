export type RiskLevel = 'GREEN' | 'YELLOW' | 'ORANGE' | 'RED';

export interface WarehouseEvent {
  id?: number;
  event_id: string;
  behaviour_type: string;
  risk_level: RiskLevel;
  confidence: number;
  detection_confidence?: number;
  behaviour_confidence?: number;
  interaction_state_sequence?: string[];
  start_timestamp: string;
  end_timestamp: string;
  duration_seconds: number;
  observed_behaviour: string;
  potential_risk: string;
  recommended_action: string;
  product_track_id?: number | null;
  person_track_id?: number | null;
  evidence_frame_path?: string | null;
  video_source?: string | null;
  metadata_json?: string | null;
  severity_reason?: string | null;
  severity_factors?: Record<string, any> | null;
  loading_bay?: string;
  is_simulated?: boolean;
  state?: 'CANDIDATE' | 'VERIFIED' | 'ACTIVE' | 'RESOLVED' | 'REJECTED';
}

export interface SummaryKPIs {
  total_events: number;
  real_events_count?: number;
  simulated_events_count?: number;
  overall_status?: string;
  items_monitored?: number;
  risk_free_observation_ratio?: number;
  at_risk_events?: number;
  potentially_protected_units?: number;
  risk_distribution: {
    GREEN: number;
    YELLOW: number;
    ORANGE: number;
    RED: number;
  };
  critical_events: number;
  high_risk_events: number;
  attention_events: number;
  handling_quality_score: number;
  top_risky_behaviour: string;
  highest_risk_bay: string;
  active_stream_status: string;
  kpi_definitions?: Record<string, string>;
}

export interface BehaviourDistItem {
  behaviour_type: string;
  title: string;
  count: number;
  risk_level: RiskLevel;
  evidence_trigger?: string;
  recommended_response?: string;
}

export interface HourlyTrendItem {
  hour: string;
  risk_events?: number;
  total?: number;
  critical: number;
  high: number;
  normal: number;
}

export interface BayStatItem {
  bay_id: string;
  name: string;
  zone_type: string;
  health_score?: number;
  risk_score: number;
  incident_count: number;
  status: string;
  primary_issue: string;
}

export interface ShiftStatItem {
  shift: string;
  shift_id: string;
  incidents: number;
  critical_count: number;
  high_risk_count: number;
  attention_count: number;
  handling_quality_score: number;
  risk_free_ratio: string;
  status: string;
  data_note?: string;
}

export interface StructuredRecommendation {
  id: string;
  what_happened: string;
  where: string;
  when: string;
  why_it_matters: string;
  what_to_change: string;
  expected_operational_effect: string;
  priority: string;
  equipment_tag?: string;
}

export interface PreventionMetrics {
  safe_handling_ratio: number;
  potential_damage_prevented?: number;
  potential_risk_exposures?: number;
  at_risk_handling_events?: number;
  recorded_risk_events?: number;
  interventions_logged: number;
  structured_recommendations?: StructuredRecommendation[];
  training_opportunities: Array<{
    id: string;
    title: string;
    priority: string;
    reason: string;
    target_bay: string;
  }>;
  recurring_risk_patterns: Array<{
    pattern: string;
    frequency: string;
    zone?: string;
  }>;
}

export interface FullDiagnosticsTelemetry {
  model: {
    name: string;
    backend: string;
    model_path: string;
    input_resolution: string;
    conf_threshold: number;
    nms_threshold: number;
    status: string;
    classes: string[];
  };
  video: {
    source: string;
    session_id: string;
    current_frame: number;
    total_frames: number;
    video_time: string;
    source_fps: number;
    render_fps: number;
    detection_fps: number;
    inference_latency_ms: number;
    tracking_latency_ms: number;
  };
  detection: {
    counts: {
      PERSON: number;
      PRODUCT: number;
      PALLET: number;
      MHE: number;
    };
    total_active: number;
    detections: Array<{
      track_id: number;
      category: string;
      label: string;
      display_label: string;
      confidence: number;
      bbox: [number, number, number, number];
    }>;
  };
  tracking: {
    active_tracks_count: number;
    tracks: Array<{
      track_id: number;
      category: string;
      label: string;
      confidence: number;
      bbox: [number, number, number, number];
      age_seconds: number;
      detection_count: number;
      missed_frames: number;
      is_grounded: boolean;
    }>;
  };
  relationship: {
    product_track_id: number | null;
    handler_track_id: number | null;
    relationship: string;
    interaction_state?: string;
    relative_motion?: [number, number, number];
    edge_distance_px: number | null;
    centroid_distance_px: number | null;
  };
  kinematics: {
    vx: number;
    vy: number;
    speed: number;
    accel_y: number;
    elevation_ratio: number;
    bottom_y: number;
    ground_state: string;
  };
  behaviour: {
    candidate: string;
    trigger_status: string;
    rules: Record<string, string>;
  };
  event: WarehouseEvent | null;
  evidence: {
    status: string;
    evidence_path: string | null;
    product_track_id: number | null;
    handler_track_id: number | null;
    timestamp: string | null;
  };
  why_this_event_fired?: {
    event_id: string;
    behaviour: string;
    risk_level: string;
    confidence: number;
    detection_confidence?: number | null;
    behaviour_confidence?: number | null;
    interaction_sequence?: string[] | null;
    trigger_conditions?: Record<string, any>;
    failed_conditions?: Record<string, any>;
    kinematics?: Record<string, any>;
    temporal?: Record<string, any>;
    debug?: Record<string, any>;
    grounded?: boolean;
    horizontal_speed?: number;
    vertical_speed?: number;
    displacement?: number;
    duration_seconds?: number;
  } | null;
}

export interface VideoState {
  session_id?: string;
  is_running: boolean;
  status: string;
  source_type: string;
  video_file?: string | null;
  active_source?: string;
  current_frame?: number;
  total_frames?: number;
  camera_index: number;
  fps: number;
  detection_fps?: number;
  inference_latency_ms?: number;
  tracking_latency_ms?: number;
  capture_fps?: number;
  active_tracks_count: number;
  total_frames_processed?: number;
  last_frame_timestamp?: string | null;
  detection_status?: string;
  tracking_status?: string;
  current_risk_level: RiskLevel;
  current_event?: WarehouseEvent | null;
  telemetry?: FullDiagnosticsTelemetry;
}
