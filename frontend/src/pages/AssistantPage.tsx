import React, { useState } from 'react';
import {
  Bot,
  Send,
  Sparkles,
  HelpCircle,
  User,
  ShieldCheck,
  ArrowRight,
  Database,
  Terminal,
  Cpu,
  CheckCircle2,
  ShieldAlert,
  AlertTriangle,
} from 'lucide-react';

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  groundingContext?: string;
  suggestedActions?: string[];
}

interface AssistantPageProps {
  onAskQuestion: (query: string) => Promise<{ reply: string; suggested_actions?: string[]; source_context?: string }>;
}

export const AssistantPage: React.FC<AssistantPageProps> = ({ onAskQuestion }) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: "Hello, Supervisor. I am **CareGuard Safety Copilot**, your operational warehouse safety intelligence assistant.\n\nI provide deterministic, grounded operational answers derived directly from **careguard.db** telemetry, kinematic vectors, and active safety policies. Every risk explanation cites exact kinematic measurements, temporal durations, and configured thresholds.\n\nSelect a recommended prompt below or ask any operational query:",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      groundingContext: "Grounded in CareGuard Telemetry (careguard.db)",
      suggestedActions: [
        "Why did the latest RED alert fire?",
        "What is the status of Bay 1?",
        "Which behaviour caused the most risk today?",
        "Which shift has the highest risk?",
        "Summarize recent incidents in Bay 1.",
        "What should the supervisor do next?",
        "Why was PRODUCT_DROPPED flagged?",
        "Are there any equipment gaps?",
      ],
    },
  ]);
  const [inputQuery, setInputQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || inputQuery;
    if (!textToSend.trim() || loading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery('');
    setLoading(true);

    try {
      const response = await onAskQuestion(textToSend);
      const assistantMsg: Message = {
        id: `assistant-${Date.now()}`,
        sender: 'assistant',
        text: response.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        groundingContext: response.source_context || "Grounded in active telemetry from careguard.db",
        suggestedActions: response.suggested_actions || [
          "Why did the latest RED alert fire?",
          "What is the status of Bay 1?",
          "What should the supervisor do next?",
        ],
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg: Message = {
        id: `assistant-err-${Date.now()}`,
        sender: 'assistant',
        text: "Encountered an issue querying the telemetry database. Please verify backend connectivity to careguard.db.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-4 animate-fade-in flex flex-col h-[calc(100vh-140px)] text-slate-800">
      {/* Header Info */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-slate-900 text-sky-400 flex items-center justify-center border border-slate-800 shadow-xs">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xs font-bold uppercase tracking-wider text-slate-900 font-mono">
                CareGuard Safety Copilot
              </h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200 font-bold">
                GROUNDED SAFETY COPILOT
              </span>
            </div>
            <p className="text-[11px] text-slate-500">Warehouse Safety Intelligence & Grounded Operational Decision Support</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded font-mono font-bold">
          <Database className="w-3.5 h-3.5 text-emerald-600" />
          <span>careguard.db ACTIVE</span>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-3.5 pr-1">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start gap-2.5 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.sender === 'assistant' && (
              <div className="w-8 h-8 rounded-md bg-slate-900 text-sky-400 flex items-center justify-center shrink-0 mt-0.5 border border-slate-800">
                <Bot className="w-4 h-4" />
              </div>
            )}
            <div className={`max-w-2xl rounded-xl p-4 text-xs leading-relaxed ${
              msg.sender === 'user'
                ? 'bg-sky-600 text-white shadow-xs'
                : 'bg-white border border-slate-200 text-slate-800 shadow-xs'
            }`}>
              <div className="whitespace-pre-line font-medium">{msg.text}</div>

              {/* Data Grounding Context Badge */}
              {msg.groundingContext && (
                <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center gap-1.5 text-[10px] font-mono text-emerald-700">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  <span>{msg.groundingContext}</span>
                </div>
              )}

              <div className={`text-[10px] mt-1.5 font-mono ${msg.sender === 'user' ? 'text-sky-200 text-right' : 'text-slate-400'}`}>
                {msg.timestamp}
              </div>

              {/* Quick Action Suggestion Chips */}
              {msg.suggestedActions && msg.suggestedActions.length > 0 && (
                <div className="mt-3 pt-2.5 border-t border-slate-100 flex flex-wrap gap-1.5">
                  {msg.suggestedActions.map((action, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSend(action)}
                      className="text-[11px] font-medium bg-slate-50 hover:bg-sky-50 text-slate-700 hover:text-sky-700 border border-slate-200 px-2.5 py-1 rounded transition-colors flex items-center gap-1"
                    >
                      <span>{action}</span>
                      <ArrowRight className="w-3 h-3 text-slate-400" />
                    </button>
                  ))}
                </div>
              )}
            </div>
            {msg.sender === 'user' && (
              <div className="w-8 h-8 rounded-md bg-slate-200 text-slate-700 flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-4 h-4" />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-md bg-slate-900 text-sky-400 flex items-center justify-center">
              <Bot className="w-4 h-4 animate-spin" />
            </div>
            <div className="bg-white border border-slate-200 rounded-lg p-3 text-xs text-slate-500 shadow-xs flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" />
              <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:0.2s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:0.4s]" />
              <span className="ml-1 font-mono text-[11px]">Grounded query on careguard.db telemetry...</span>
            </div>
          </div>
        )}
      </div>

      {/* Input Box */}
      <div className="bg-white rounded-xl border border-slate-200 p-2 flex items-center gap-2 shadow-xs">
        <input
          type="text"
          placeholder="Ask CareGuard Safety Copilot (e.g. 'Why did the latest RED alert fire?' or 'What is the status of Bay 1?')..."
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSend();
          }}
          className="flex-1 text-xs px-3 py-2 bg-transparent focus:outline-none placeholder:text-slate-400 text-slate-800 font-medium"
        />
        <button
          disabled={!inputQuery.trim() || loading}
          onClick={() => handleSend()}
          className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white font-semibold text-xs transition-colors flex items-center gap-1.5 shadow-xs"
        >
          <Send className="w-3.5 h-3.5" />
          <span>Send</span>
        </button>
      </div>
    </div>
  );
};

