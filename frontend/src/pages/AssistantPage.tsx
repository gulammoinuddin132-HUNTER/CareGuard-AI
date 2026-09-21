import React, { useState, useRef, useEffect } from 'react';
import {
  Bot,
  Send,
  Sparkles,
  Database,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Activity,
  ShieldCheck,
  ExternalLink,
  RotateCcw,
  User,
  Sliders,
  Layers,
} from 'lucide-react';

export interface StructuredTelemetry {
  handling_quality_score?: number;
  total_events?: number;
  critical_events?: number;
  high_risk_events?: number;
  event_id?: string;
  bay_id?: string;
  behavior_type?: string;
  kinematic_confidence?: number;
  [key: string]: any;
}

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  groundingContext?: string;
  suggestedActions?: string[];
  structuredData?: StructuredTelemetry;
}

interface AssistantPageProps {
  onAskQuestion: (
    query: string,
    history?: Array<{ sender: string; text: string }>
  ) => Promise<{
    reply: string;
    structured_data?: Record<string, any>;
    suggested_actions?: string[];
    source_context?: string;
  }>;
  onNavigateToIncident?: (eventId: string) => void;
}

export const AssistantPage: React.FC<AssistantPageProps> = ({
  onAskQuestion,
  onNavigateToIncident,
}) => {
  const initialMessage: Message = {
    id: 'welcome',
    sender: 'assistant',
    text: `Hello Supervisor. I am the **CareGuard Safety Copilot** — your data-grounded warehouse safety operations assistant.

I answer operational questions using live telemetry, kinematic trajectories, bay statistics, and logged incidents directly from **careguard.db**.

### How I can help:
- **Quality & Scores**: Explain Handling Quality scores, penalty breakdowns, and trend shifts.
- **Incident Diagnostics**: Break down why specific RED/AMBER alerts (e.g. \`PRODUCT_DROPPED\`, \`HEAVY_LIFT_SOLO\`) were flagged with exact kinematic evidence.
- **Bay & Shift Analytics**: Compare bay risk levels, identify high-frequency hazard zones, and evaluate shift metrics.
- **Actionable Guidance**: Recommend targeted floor interventions and training priorities.

Select a quick query below or ask any operational safety question:`,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    groundingContext: 'careguard.db (safety_events, telemetry_log, bay_metrics)',
    suggestedActions: [
      'Why is our Handling Quality score at this level?',
      'Explain the latest critical safety event',
      'Which bay has the most drops or improper handling?',
      'What are our top 3 most frequent risky behaviours?',
      'Compare shift risks and recommend supervisor actions',
      'Why was PRODUCT_DROPPED flagged in recent footage?',
      'Are there any equipment compliance gaps?',
      'What actions should the floor supervisor take right now?',
    ],
  };

  const [messages, setMessages] = useState<Message[]>([initialMessage]);
  const [inputQuery, setInputQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || inputQuery;
    if (!textToSend.trim() || loading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInputQuery('');
    setLoading(true);

    // Build conversation history format for contextual follow-ups
    const conversationHistory = newMessages.map((m) => ({
      sender: m.sender,
      text: m.text,
    }));

    try {
      const response = await onAskQuestion(textToSend, conversationHistory);
      const assistantMsg: Message = {
        id: `assistant-${Date.now()}`,
        sender: 'assistant',
        text: response.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        groundingContext: response.source_context || 'Grounded in active telemetry from careguard.db',
        suggestedActions: response.suggested_actions || [
          'Explain the latest critical safety event',
          'Which bay has the highest risk today?',
          'What actions should the supervisor take right now?',
        ],
        structuredData: response.structured_data,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg: Message = {
        id: `assistant-err-${Date.now()}`,
        sender: 'assistant',
        text: 'Unable to query the telemetry database right now. Please verify backend connectivity to careguard.db.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleResetChat = () => {
    setMessages([initialMessage]);
    setInputQuery('');
  };

  // Helper to render text with event ID navigation pills and markdown formatting
  const renderMessageContent = (text: string) => {
    // Split by lines to handle headers and bullet points
    const lines = text.split('\n');

    return (
      <div className="space-y-2 text-sm leading-relaxed">
        {lines.map((line, lineIdx) => {
          if (!line.trim()) {
            return <div key={lineIdx} className="h-2" />;
          }

          // Headers
          if (line.startsWith('### ')) {
            return (
              <h4 key={lineIdx} className="font-bold text-slate-900 text-sm mt-3 mb-1 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-sky-600" />
                {line.replace('### ', '')}
              </h4>
            );
          }
          if (line.startsWith('## ')) {
            return (
              <h3 key={lineIdx} className="font-extrabold text-slate-900 text-base mt-3 mb-1 border-b border-slate-100 pb-1">
                {line.replace('## ', '')}
              </h3>
            );
          }

          // Bullet points
          const isBullet = line.trim().startsWith('- ') || line.trim().startsWith('* ');
          const formattedLine = isBullet ? line.trim().substring(2) : line;

          // Parse markdown segments (**bold**, `code`, [EVT-...])
          const parts = formattedLine.split(/(\*\*.*?\*\*|`.*?`)/g);

          return (
            <div key={lineIdx} className={isBullet ? 'flex items-start gap-2 pl-2' : ''}>
              {isBullet && <span className="text-sky-500 font-bold mt-1 text-xs">•</span>}
              <div className="flex-1">
                {parts.map((part, partIdx) => {
                  if (part.startsWith('**') && part.endsWith('**')) {
                    return (
                      <strong key={partIdx} className="font-bold text-slate-900">
                        {part.slice(2, -2)}
                      </strong>
                    );
                  }
                  if (part.startsWith('`') && part.endsWith('`')) {
                    const codeVal = part.slice(1, -1);
                    // Check if code contains an EVT- or incident ID
                    const isEventCode = codeVal.startsWith('EVT-') || codeVal.includes('EVT-');
                    if (isEventCode && onNavigateToIncident) {
                      return (
                        <button
                          key={partIdx}
                          onClick={() => onNavigateToIncident(codeVal)}
                          className="inline-flex items-center gap-1 mx-1 px-2 py-0.5 rounded bg-sky-100 hover:bg-sky-200 text-sky-800 font-mono text-xs font-semibold border border-sky-300 transition-colors"
                          title="Click to view this event in Safety Events"
                        >
                          <span>{codeVal}</span>
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      );
                    }
                    return (
                      <code
                        key={partIdx}
                        className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-800 font-mono text-xs border border-slate-200"
                      >
                        {codeVal}
                      </code>
                    );
                  }
                  return <span key={partIdx}>{part}</span>;
                })}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="max-w-5xl mx-auto space-y-4 animate-fade-in flex flex-col h-[calc(100vh-140px)] text-slate-800">
      {/* Copilot Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-slate-900 text-sky-400 flex items-center justify-center border border-slate-800 shadow-xs">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-black text-slate-900 tracking-tight font-sans">
                CareGuard Safety Copilot
              </h1>
              <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-sky-50 text-sky-700 border border-sky-200 flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-sky-500" />
                Data-Grounded Reasoning
              </span>
            </div>
            <p className="text-xs text-slate-500 font-medium">
              Zero-hallucination operational safety intelligence derived from active telemetry and safety policies
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleResetChat}
            className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 border border-slate-200 px-3 py-1.5 rounded-lg font-medium transition-colors"
            title="Reset conversation"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset Chat</span>
          </button>
          <div className="flex items-center gap-2 text-xs text-emerald-800 bg-emerald-50 border border-emerald-300 px-3.5 py-1.5 rounded-lg font-mono font-bold">
            <Database className="w-3.5 h-3.5 text-emerald-600" />
            <span>careguard.db CONNECTED</span>
          </div>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start gap-3 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.sender === 'assistant' && (
              <div className="w-8 h-8 rounded-lg bg-slate-900 text-sky-400 flex items-center justify-center shrink-0 mt-0.5 border border-slate-800">
                <Bot className="w-4 h-4" />
              </div>
            )}
            <div
              className={`max-w-3xl rounded-xl p-4 text-sm leading-relaxed ${
                msg.sender === 'user'
                  ? 'bg-sky-600 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-800 shadow-xs'
              }`}
            >
              {/* Message Body */}
              {msg.sender === 'user' ? (
                <div className="font-medium whitespace-pre-line">{msg.text}</div>
              ) : (
                renderMessageContent(msg.text)
              )}

              {/* Structured Telemetry Data Card (if provided by Copilot) */}
              {msg.structuredData && Object.keys(msg.structuredData).length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {msg.structuredData.handling_quality_score !== undefined && (
                    <div className="bg-slate-50 border border-slate-200 rounded-lg p-2 text-center">
                      <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">
                        Quality Score
                      </div>
                      <div className="text-base font-black text-slate-900 font-mono">
                        {msg.structuredData.handling_quality_score}/100
                      </div>
                    </div>
                  )}
                  {msg.structuredData.critical_events !== undefined && (
                    <div className="bg-rose-50 border border-rose-200 rounded-lg p-2 text-center">
                      <div className="text-[10px] font-semibold text-rose-700 uppercase tracking-wide">
                        Critical Events
                      </div>
                      <div className="text-base font-black text-rose-800 font-mono">
                        {msg.structuredData.critical_events}
                      </div>
                    </div>
                  )}
                  {msg.structuredData.event_id && (
                    <div className="bg-sky-50 border border-sky-200 rounded-lg p-2 text-center">
                      <div className="text-[10px] font-semibold text-sky-700 uppercase tracking-wide">
                        Target Event
                      </div>
                      <button
                        onClick={() =>
                          onNavigateToIncident && onNavigateToIncident(msg.structuredData!.event_id!)
                        }
                        className="text-xs font-bold text-sky-900 font-mono underline hover:text-sky-700"
                      >
                        {msg.structuredData.event_id}
                      </button>
                    </div>
                  )}
                  {msg.structuredData.bay_id && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 text-center">
                      <div className="text-[10px] font-semibold text-amber-700 uppercase tracking-wide">
                        Bay Location
                      </div>
                      <div className="text-xs font-bold text-amber-900 font-mono">
                        {msg.structuredData.bay_id}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Data Grounding Context Badge */}
              {msg.groundingContext && (
                <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] font-mono text-emerald-700">
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span>{msg.groundingContext}</span>
                  </div>
                  <span className="text-[10px] text-slate-400 font-sans">{msg.timestamp}</span>
                </div>
              )}

              {/* Quick Action Suggestion Chips */}
              {msg.suggestedActions && msg.suggestedActions.length > 0 && (
                <div className="mt-3 pt-2.5 border-t border-slate-100 flex flex-wrap gap-1.5">
                  {msg.suggestedActions.map((action, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSend(action)}
                      className="text-[11px] font-medium bg-slate-50 hover:bg-sky-50 text-slate-700 hover:text-sky-700 border border-slate-200 px-2.5 py-1 rounded-md transition-colors flex items-center gap-1"
                    >
                      <span>{action}</span>
                      <ArrowRight className="w-3 h-3 text-slate-400" />
                    </button>
                  ))}
                </div>
              )}
            </div>
            {msg.sender === 'user' && (
              <div className="w-8 h-8 rounded-lg bg-slate-200 text-slate-700 flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-4 h-4" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-slate-900 text-sky-400 flex items-center justify-center">
              <Bot className="w-4 h-4 animate-spin" />
            </div>
            <div className="bg-white border border-slate-200 rounded-lg p-3 text-xs text-slate-600 shadow-xs flex items-center gap-2.5">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-bounce" />
              <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-bounce [animation-delay:0.2s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-bounce [animation-delay:0.4s]" />
              <span className="ml-1 font-mono text-[11px] text-slate-700 font-medium">
                Analyzing careguard.db telemetry, bay statistics, and policy thresholds...
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <div className="bg-white rounded-xl border border-slate-200 p-2.5 flex items-center gap-2 shadow-xs">
        <input
          type="text"
          placeholder="Ask Safety Copilot (e.g. 'Why is our Handling Quality score 78?', 'Explain latest critical drop', 'Compare bay risks')..."
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSend();
          }}
          className="flex-1 text-xs sm:text-sm px-3 py-2 bg-transparent focus:outline-none placeholder:text-slate-400 text-slate-800 font-medium"
        />
        <button
          disabled={!inputQuery.trim() || loading}
          onClick={() => handleSend()}
          className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white font-semibold text-xs sm:text-sm transition-colors flex items-center gap-1.5 shadow-xs"
        >
          <Send className="w-3.5 h-3.5" />
          <span>Send</span>
        </button>
      </div>
    </div>
  );
};
