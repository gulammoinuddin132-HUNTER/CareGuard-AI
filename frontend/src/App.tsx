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
    let pollCount = 0;
    const timer = setInterval(async () => {
      if (isUploadingRef.current) return;
      try {
        const state = await api.getVideoState();
        setVideoState(state);

        pollCount += 1;
        const currentEvtId = state.current_event?.event_id;
        const eventChanged = currentEvtId && currentEvtId !== lastSeenEventId;
        
        // Refresh full overview every ~4.8s (4 ticks) or immediately when an active event changes
        if (eventChanged || pollCount % 4 === 0) {
          if (eventChanged) {
            lastSeenEventId = currentEvtId;
          }
          const [incidentsData, overviewData] = await Promise.all([
            api.getIncidents({ limit: 100 }),
            api.getOverview(),
          ]);
          setAllIncidents(incidentsData.incidents);
          setRecentIncidents(overviewData.recent_incidents);
          setSummary(overviewData.summary);
          setBehaviourDist(overviewData.behaviour_distribution);
          setHourlyTrends(overviewData.hourly_trends);
          setBayStats(overviewData.bay_stats);
          setShiftStats(overviewData.shift_stats || []);
          setPrevention(overviewData.prevention_metrics);
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

  const handleAskAssistant = async (
    message: string,
    history?: Array<{ sender: string; text: string }>
  ) => {
    return api.askAssistant(message, history);
  };

  const handleNavigateToIncident = (eventId: string) => {
    const cleanId = eventId.trim();
    const found = allIncidents.find(
      (inc) => inc.event_id === cleanId || inc.event_id.includes(cleanId)
    );
    if (found) {
      setSelectedIncident(found);
    } else {
      // Create lightweight placeholder incident for the view
      const now = new Date().toISOString();
      setSelectedIncident({
        event_id: cleanId,
        behaviour_type: 'PRODUCT_DROPPED',
        risk_level: 'RED',
        confidence: 0.95,
        start_timestamp: now,
        end_timestamp: now,
        duration_seconds: 1.2,
        observed_behaviour: `Incident ${cleanId} referenced during Safety Copilot session.`,
        potential_risk: 'Ground impact and package structural compromise.',
        recommended_action: 'Perform physical goods inspection and verify handler safety compliance.',
        loading_bay: 'Bay 1',
        product_track_id: 1,
        person_track_id: 1,
      });
    }
    setCurrentTab('incidents');
  };

  const handleSaveSettings = async (settings: any) => {
    await api.updateSettings(settings);
    await loadData();
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <Header
        videoState={videoState}
        qualityScore={summary?.handling_quality_score}
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
              onNavigateToIncident={handleNavigateToIncident}
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
