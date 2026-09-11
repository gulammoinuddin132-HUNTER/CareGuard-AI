import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Header } from './components/layout/Header';
import { Sidebar, TabType } from './components/layout/Sidebar';
import { OverviewPage } from './pages/OverviewPage';
import { LiveMonitoringPage } from './pages/LiveMonitoringPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { PreventionPage } from './pages/PreventionPage';
import { AssistantPage } from './pages/AssistantPage';
import { SettingsPage } from './pages/SettingsPage';
import { api } from './services/api';
import {
  SummaryKPIs,
  WarehouseEvent,
  BehaviourDistItem,
  HourlyTrendItem,
  BayStatItem,
  ShiftStatItem,
  PreventionMetrics,
  VideoState,
} from './types/warehouse';

export const App: React.FC = () => {
  const getInitialTab = (): TabType => {
    const hash = window.location.hash.replace('#', '').toLowerCase();
    if (hash === 'live' || hash === 'monitoring') return 'monitoring';
    if (['overview', 'incidents', 'analytics', 'prevention', 'assistant', 'settings'].includes(hash)) {
      return hash as TabType;
    }
    const params = new URLSearchParams(window.location.search);
    const tabParam = params.get('tab')?.toLowerCase();
    if (tabParam === 'live' || tabParam === 'monitoring') return 'monitoring';
    if (tabParam && ['overview', 'incidents', 'analytics', 'prevention', 'assistant', 'settings'].includes(tabParam)) {
      return tabParam as TabType;
    }
    return 'overview';
  };

  const [currentTab, setCurrentTab] = useState<TabType>(getInitialTab);
  const [summary, setSummary] = useState<SummaryKPIs | null>(null);
  const [recentIncidents, setRecentIncidents] = useState<WarehouseEvent[]>([]);
  const [allIncidents, setAllIncidents] = useState<WarehouseEvent[]>([]);
  const [behaviourDist, setBehaviourDist] = useState<BehaviourDistItem[]>([]);
  const [hourlyTrends, setHourlyTrends] = useState<HourlyTrendItem[]>([]);
  const [bayStats, setBayStats] = useState<BayStatItem[]>([]);
  const [shiftStats, setShiftStats] = useState<ShiftStatItem[]>([]);
  const [prevention, setPrevention] = useState<PreventionMetrics | null>(null);
  const [videoState, setVideoState] = useState<VideoState | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<WarehouseEvent | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const isUploadingRef = useRef<boolean>(false);

  // Load all initial backend telemetry
  const loadData = useCallback(async () => {
    try {
      const [overviewData, incidentsData, stateData] = await Promise.all([
        api.getOverview(),
        api.getIncidents({ limit: 100 }),
        api.getVideoState(),
      ]);

      setSummary(overviewData.summary);
      setRecentIncidents(overviewData.recent_incidents);
      setBehaviourDist(overviewData.behaviour_distribution);
      setHourlyTrends(overviewData.hourly_trends);
      setBayStats(overviewData.bay_stats);
      setShiftStats(overviewData.shift_stats || []);
      setPrevention(overviewData.prevention_metrics);
      setAllIncidents(incidentsData.incidents);
      setVideoState(stateData);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    // Periodic poll for video state & live incident stream synchronization
    let lastSeenEventId: string | null = null;
    const timer = setInterval(async () => {
      if (isUploadingRef.current) return;
      try {
        const state = await api.getVideoState();
        setVideoState(state);

        // If a new event is detected or active event changes, automatically sync audit log & KPIs
        const currentEvtId = state.current_event?.event_id;
        if (currentEvtId && currentEvtId !== lastSeenEventId) {
          lastSeenEventId = currentEvtId;
          const [incidentsData, overviewData] = await Promise.all([
            api.getIncidents({ limit: 100 }),
            api.getOverview(),
          ]);
          setAllIncidents(incidentsData.incidents);
          setRecentIncidents(overviewData.recent_incidents);
          setSummary(overviewData.summary);
          setBehaviourDist(overviewData.behaviour_distribution);
        }
      } catch {
        // ignore fetch failures during transitions
      }
    }, 1200);

    return () => clearInterval(timer);
  }, [loadData]);

  // Controls
  const handleTogglePlay = async () => {
    if (!videoState) return;
    const nextAction = videoState.is_running ? 'stop' : 'start';
    await api.controlVideo(nextAction);
    const updated = await api.getVideoState();
    setVideoState(updated);
  };

  const handleUploadVideo = async (file: File) => {
    isUploadingRef.current = true;
    try {
      await api.uploadVideo(file);
      await loadData();
      setCurrentTab('monitoring');
    } finally {
      isUploadingRef.current = false;
    }
  };

  const handleTriggerSimulation = async (presetId: number) => {
    await api.triggerSimulation(presetId);
    await loadData();
  };

  const handleSelectSource = async (sourceType: 'file' | 'camera' | 'synthetic', pathOrIdx?: string | number) => {
    await api.setVideoSource(sourceType, pathOrIdx);
    await loadData();
  };

  const handleLogAction = async (eventId: string, note: string) => {
    await api.logIncidentAction(eventId, note);
    await loadData();
  };

  const handleAskAssistant = async (message: string) => {
    return api.askAssistant(message);
  };

  const handleSaveSettings = async (settings: any) => {
    await api.updateSettings(settings);
    await loadData();
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <Header
        videoState={videoState}
        qualityScore={summary?.handling_quality_score || 88}
        onRefresh={loadData}
        onTogglePlay={handleTogglePlay}
      />

      <div className="flex-1 flex">
        <Sidebar
          currentTab={currentTab}
          onSelectTab={setCurrentTab}
          criticalCount={summary?.critical_events || 0}
        />

        <main className="flex-1 p-6 overflow-y-auto max-h-[calc(100vh-61px)]">
          {currentTab === 'overview' && (
            <OverviewPage
              summary={summary}
              recentIncidents={recentIncidents}
              behaviourDist={behaviourDist}
              hourlyTrends={hourlyTrends}
              bayStats={bayStats}
              prevention={prevention}
              videoState={videoState}
              onNavigateToMonitoring={() => setCurrentTab('monitoring')}
              onSelectIncident={(inc) => {
                setSelectedIncident(inc);
                setCurrentTab('incidents');
              }}
            />
          )}

          {currentTab === 'monitoring' && (
            <LiveMonitoringPage
              videoState={videoState}
              onTogglePlay={handleTogglePlay}
              onUploadVideo={handleUploadVideo}
              onTriggerSimulation={handleTriggerSimulation}
              onSelectSource={handleSelectSource}
            />
          )}

          {currentTab === 'incidents' && (
            <IncidentsPage
              incidents={allIncidents}
              selectedIncident={selectedIncident}
              onSelectIncident={setSelectedIncident}
              onLogAction={handleLogAction}
            />
          )}

          {currentTab === 'analytics' && (
            <AnalyticsPage
              behaviourDist={behaviourDist}
              bayStats={bayStats}
              shiftStats={shiftStats}
            />
          )}

          {currentTab === 'prevention' && (
            <PreventionPage
              prevention={prevention}
              summary={summary}
            />
          )}

          {currentTab === 'assistant' && (
            <AssistantPage
              onAskQuestion={handleAskAssistant}
            />
          )}

          {currentTab === 'settings' && (
            <SettingsPage
              onSaveSettings={handleSaveSettings}
            />
          )}
        </main>
      </div>
    </div>
  );
};
