import {
  SummaryKPIs,
  WarehouseEvent,
  BehaviourDistItem,
  HourlyTrendItem,
  BayStatItem,
  ShiftStatItem,
  PreventionMetrics,
  VideoState,
} from '../types/warehouse';

const BASE_URL = '/api';

export const api = {
  // Overview
  getOverview: async (): Promise<{
    summary: SummaryKPIs;
    recent_incidents: WarehouseEvent[];
    behaviour_distribution: BehaviourDistItem[];
    hourly_trends: HourlyTrendItem[];
    bay_stats: BayStatItem[];
    prevention_metrics: PreventionMetrics;
    shift_stats: ShiftStatItem[];
  }> => {
    const res = await fetch(`${BASE_URL}/overview`);
    if (!res.ok) throw new Error('Failed to fetch overview data');
    return res.json();
  },

  // Video State & Controls
  getVideoState: async (): Promise<VideoState> => {
    const res = await fetch(`${BASE_URL}/video/state`);
    if (!res.ok) throw new Error('Failed to fetch video state');
    return res.json();
  },

  controlVideo: async (action: 'start' | 'stop'): Promise<{ status: string; is_running: boolean }> => {
    const form = new FormData();
    form.append('action', action);
    const res = await fetch(`${BASE_URL}/video/control`, { method: 'POST', body: form });
    if (!res.ok) throw new Error('Failed to control video');
    return res.json();
  },

  setVideoSource: async (sourceType: 'file' | 'camera' | 'synthetic', pathOrIdx?: string | number) => {
    const form = new FormData();
    form.append('source_type', sourceType);
    if (sourceType === 'file' && pathOrIdx) form.append('video_path', String(pathOrIdx));
    if (sourceType === 'camera' && typeof pathOrIdx === 'number') form.append('camera_index', String(pathOrIdx));
    const res = await fetch(`${BASE_URL}/video/source`, { method: 'POST', body: form });
    if (!res.ok) throw new Error('Failed to switch video source');
    return res.json();
  },

  uploadVideo: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
    }, 60000);
    try {
      const res = await fetch(`${BASE_URL}/video/upload`, {
        method: 'POST',
        body: form,
        signal: controller.signal,
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to upload video');
      }
      return res.json();
    } catch (err: any) {
      if (err.name === 'AbortError' || (err.message && err.message.toLowerCase().includes('abort'))) {
        throw new Error('Video upload request was aborted or timed out after 60s. Please try again.');
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  },

  setOverlayMode: async (mode: string) => {
    const form = new FormData();
    form.append('mode', mode);
    const res = await fetch(`${BASE_URL}/video/overlay`, { method: 'POST', body: form });
    if (!res.ok) throw new Error('Failed to set overlay mode');
    return res.json();
  },

  listAvailableVideos: async (): Promise<Array<{ filename: string; path: string; size_mb: number }>> => {
    const res = await fetch(`${BASE_URL}/video/files`);
    if (!res.ok) return [];
    return res.json();
  },

  // Incidents
  getIncidents: async (params?: { risk_level?: string; behaviour_type?: string; search?: string; limit?: number }): Promise<{ count: number; incidents: WarehouseEvent[] }> => {
    const searchParams = new URLSearchParams();
    if (params?.risk_level && params.risk_level !== 'ALL') searchParams.append('risk_level', params.risk_level);
    if (params?.behaviour_type && params.behaviour_type !== 'ALL') searchParams.append('behaviour_type', params.behaviour_type);
    if (params?.search) searchParams.append('search', params.search);
    if (params?.limit) searchParams.append('limit', String(params.limit));

    const res = await fetch(`${BASE_URL}/incidents?${searchParams.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch incidents');
    return res.json();
  },

  getIncidentDetails: async (eventId: string): Promise<WarehouseEvent> => {
    const res = await fetch(`${BASE_URL}/incidents/${eventId}`);
    if (!res.ok) throw new Error('Failed to fetch incident details');
    return res.json();
  },

  logIncidentAction: async (eventId: string, note: string) => {
    const form = new FormData();
    form.append('action_note', note);
    const res = await fetch(`${BASE_URL}/incidents/${eventId}/action`, { method: 'POST', body: form });
    if (!res.ok) throw new Error('Failed to log action');
    return res.json();
  },

  // Analytics
  getAnalytics: async () => {
    const res = await fetch(`${BASE_URL}/analytics`);
    if (!res.ok) throw new Error('Failed to fetch analytics');
    return res.json();
  },

  // Prevention
  getPrevention: async () => {
    const res = await fetch(`${BASE_URL}/prevention`);
    if (!res.ok) throw new Error('Failed to fetch prevention data');
    return res.json();
  },

  // Assistant Chat
  askAssistant: async (message: string): Promise<{ reply: string; suggested_actions?: string[] }> => {
    const res = await fetch(`${BASE_URL}/assistant/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    if (!res.ok) throw new Error('Failed to ask assistant');
    return res.json();
  },

  // Simulator Trigger
  triggerSimulation: async (presetId: number) => {
    const form = new FormData();
    form.append('preset_id', String(presetId));
    const res = await fetch(`${BASE_URL}/simulator/trigger`, { method: 'POST', body: form });
    if (!res.ok) throw new Error('Failed to trigger simulation');
    return res.json();
  },

  // Settings
  getSettings: async () => {
    const res = await fetch(`${BASE_URL}/settings`);
    if (!res.ok) throw new Error('Failed to fetch settings');
    return res.json();
  },

  updateSettings: async (settings: any) => {
    const res = await fetch(`${BASE_URL}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    if (!res.ok) throw new Error('Failed to update settings');
    return res.json();
  },
};
