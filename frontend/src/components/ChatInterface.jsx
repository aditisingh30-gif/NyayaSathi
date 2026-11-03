import React, { useState, useEffect, useRef } from 'react';
import {
  Scale,
  Send,
  Plus,
  Trash2,
  RefreshCw,
  AlertCircle,
  FileText,
  Bookmark,
  ShieldCheck,
  Cpu,
  Sparkles,
  MessageSquare,
  HelpCircle,
  Clock,
  ChevronRight,
  Menu,
  X
} from 'lucide-react';
import {
  sendChatMessage,
  fetchConversations,
  fetchConversation,
  deleteConversation
} from '../services/api';
import CitationCard from './CitationCard';

const SAMPLE_PROMPTS = [
  {
    lang: 'English',
    text: 'Who is defined as a consumer under the Consumer Protection Act, 2019?'
  },
  {
    lang: 'English',
    text: 'What is the procedure under Section 35 for filing a complaint before the District Commission?'
  },
  {
    lang: 'Hindi',
    text: 'उपभोक्ता संरक्षण अधिनियम के तहत शिकायत दर्ज करने की समय सीमा क्या है?'
  },
  {
    lang: 'Hinglish',
    text: 'Kharab product ya misleading advertisement par consumer ko kya rights milte hain?'
  },
  {
    lang: 'English',
    text: 'What constitutes product liability under the Consumer Protection Act?'
  }
];

export default function ChatInterface() {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState(null);
  const [lastFailedQuery, setLastFailedQuery] = useState(null);
  const [selectedProvider, setSelectedProvider] = useState('auto');
  const [sidebarOpen, setSidebarOpen] = useState(
    () => window.innerWidth >= 768
  );

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Load conversations on mount
  useEffect(() => {
    loadConversationList();
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Dynamic loading indicator messages
  useEffect(() => {
    let timer;
    if (loading) {
      setLoadingStep(0);
      timer = setInterval(() => {
        setLoadingStep((prev) => (prev + 1) % 3);
      }, 1800);
    }
    return () => clearInterval(timer);
  }, [loading]);

  const loadConversationList = async () => {
    try {
      const data = await fetchConversations();
      setConversations(data || []);
    } catch (err) {
      console.error('Failed to load conversation history:', err);
    }
  };

  const handleSelectConversation = async (convId) => {
    if (convId === activeConversationId) return;
    try {
      setLoading(true);
      setError(null);
      const detail = await fetchConversation(convId);
      setActiveConversationId(convId);
      setMessages(detail.messages || []);
      if (window.innerWidth < 768) setSidebarOpen(false);
    } catch (err) {
      setError(`Failed to load conversation: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleNewConversation = () => {
    if (window.innerWidth < 768) setSidebarOpen(false);
    setActiveConversationId(null);
    setMessages([]);
    setError(null);
    setLastFailedQuery(null);
    inputRef.current?.focus();
  };

  const handleDeleteConversation = async (e, convId) => {
    e.stopPropagation();
    try {
      await deleteConversation(convId);
      if (activeConversationId === convId) {
        handleNewConversation();
      }
      await loadConversationList();
    } catch (err) {
      setError(`Failed to delete conversation: ${err.message}`);
    }
  };

  const handleSendMessage = async (textToSend = null) => {
    const query = (textToSend || inputQuery).trim();
    if (!query || loading) return;

    // Optimistically append user message
    const tempUserMsg = {
      id: `usr_${Date.now()}`,
      role: 'user',
      content: query,
      created_at: new Date().toISOString()
    };

    setMessages((prev) => [...prev, tempUserMsg]);
    setInputQuery('');
    setLoading(true);
    setError(null);
    setLastFailedQuery(null);

    try {
      const providerParam = selectedProvider === 'auto' ? null : selectedProvider;
      const response = await sendChatMessage(query, activeConversationId, providerParam);

      // Set active conversation ID if newly created
      if (!activeConversationId && response.conversation_id) {
        setActiveConversationId(response.conversation_id);
      }

      // Append assistant message
      const assistantMsg = {
        id: `asst_${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        direct_answer: response.direct_answer,
        legal_explanation: response.legal_explanation,
        citations: response.citations || [],
        disclaimer: response.disclaimer,
        provider_used: response.provider_used,
        processing_time_seconds: response.processing_time_seconds,
        created_at: new Date().toISOString()
      };

      setMessages((prev) => [...prev, assistantMsg]);
      await loadConversationList();
    } catch (err) {
      setError(err.message || 'Chat service encountered an error.');
      setLastFailedQuery(query);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handlePromptClick = (promptText) => {
    setInputQuery(promptText);
    handleSendMessage(promptText);
  };

  const loadingSteps = [
    'Retrieving statutory provisions from ChromaDB vector store...',
    'Evaluating statutory section numbers and relevance thresholds...',
    'Synthesizing evidence-grounded legal explanation...'
  ];

  return (
    <div className="relative min-w-0 flex-1 flex overflow-hidden bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl h-[calc(100vh-140px)] max-md:h-[calc(100dvh-100px)] max-md:rounded-xl">
      {/* Sidebar: Conversation Sessions */}
      <aside
        className={`${
          sidebarOpen
            ? 'w-72 max-md:absolute max-md:inset-y-0 max-md:left-0 max-md:w-[min(18rem,85vw)] max-md:shadow-2xl'
            : 'w-0'
        } shrink-0 duration-300 ease-in-out transition-all border-r border-slate-800 bg-slate-950/95 flex flex-col overflow-hidden z-20`}
      >
        <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <MessageSquare className="w-4 h-4 text-amber-400" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Legal Inquiries
            </span>
          </div>
          <button
            onClick={handleNewConversation}
            className="p-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 transition flex items-center space-x-1 text-xs"
            title="Start new inquiry"
          >
            <Plus className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">New</span>
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-500 px-4">
              <MessageSquare className="w-8 h-8 mx-auto text-slate-700 mb-2" />
              <span>No prior legal inquiries. Start a new session below.</span>
            </div>
          ) : (
            conversations.map((c) => (
              <div
                key={c.conversation_id}
                onClick={() => handleSelectConversation(c.conversation_id)}
                className={`group px-3 py-2.5 rounded-xl cursor-pointer flex items-center justify-between text-xs transition ${
                  activeConversationId === c.conversation_id
                    ? 'bg-amber-500/15 border border-amber-500/30 text-amber-300 font-semibold'
                    : 'hover:bg-slate-900 text-slate-400 hover:text-slate-200 border border-transparent'
                }`}
              >
                <div className="truncate pr-2">
                  <div className="truncate">{c.title || 'Legal Inquiry'}</div>
                  <div className="text-[10px] text-slate-500 flex items-center space-x-2 mt-0.5 font-normal">
                    <span>{c.message_count} messages</span>
                  </div>
                </div>
                <button
                  onClick={(e) => handleDeleteConversation(e, c.conversation_id)}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition"
                  title="Delete conversation"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Sidebar Footer */}
        <div className="p-3 border-t border-slate-800 text-[11px] text-slate-500 flex items-center justify-between">
          <span className="flex items-center space-x-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>ChromaDB Grounded</span>
          </span>
          <span className="font-mono text-slate-400">{conversations.length} Sessions</span>
        </div>
      </aside>

      {/* Mobile backdrop: tap outside the drawer to close it */}
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close conversation sidebar"
          onClick={() => setSidebarOpen(false)}
          className="absolute inset-0 z-10 bg-black/50 md:hidden"
        />
      )}

      {/* Main Chat Workspace */}
      <div className="min-w-0 flex-1 flex flex-col bg-slate-900/60 overflow-hidden">
        {/* Chat Header */}
        <header className="min-h-14 px-2 sm:px-4 py-2 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center space-x-2 sm:space-x-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-slate-200 transition"
              title="Toggle sessions sidebar"
            >
              <Menu className="w-4 h-4" />
            </button>
            <div>
              <div className="min-w-0 text-xs sm:text-sm font-bold text-slate-200 flex items-center gap-1.5 sm:gap-2">
                <span className="truncate">NyayaSathi</span>
                <span className="shrink-0 text-[9px] sm:text-[10px] bg-emerald-950/60 text-emerald-400 border border-emerald-800/50 px-1.5 sm:px-2 py-0.5 rounded-full font-mono">
                  Online
                </span>
              </div>
              <div className="hidden sm:block text-[10px] text-slate-500">
                Legal Consultation
              </div>
            </div>
          </div>

          <div className="flex shrink-0 items-center space-x-1.5 sm:space-x-3">
            {/* LLM Provider Selection */}
            <div className="flex items-center space-x-1.5">
              <Cpu className="w-3.5 h-3.5 text-slate-400 hidden sm:inline" />
              <select
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value)}
                className="max-w-[116px] sm:max-w-none bg-slate-900 border border-slate-700/80 rounded-lg px-1.5 sm:px-2.5 py-1 text-[10px] sm:text-xs text-slate-300 focus:outline-none focus:border-amber-500"
                title="Select LLM Provider"
              >
                <option value="auto">Provider: Auto-Detect</option>
                <option value="gemini">Google Gemini</option>
                <option value="openai">OpenAI GPT</option>
                <option value="ollama">Local Ollama</option>
                <option value="fallback">Grounded Synthesizer</option>
              </select>
            </div>

            {messages.length > 0 && (
              <button
                onClick={handleNewConversation}
                className="text-xs px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
              >
                Clear
              </button>
            )}
          </div>
        </header>

        {/* Message Feed Area */}
        <div className="min-w-0 flex-1 overflow-y-auto p-3 sm:p-6 space-y-5 sm:space-y-6">
          {messages.length === 0 ? (
            /* Welcome / Empty State */
            <div className="max-w-2xl mx-auto text-center py-8 space-y-6">
              <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center mx-auto shadow-xl shadow-amber-500/5">
                <Scale className="w-8 h-8" />
              </div>

              <div>
                <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                  Welcome to NyayaSathi
                </h2>
                <p className="text-xs sm:text-sm text-slate-400 mt-1.5 max-w-lg mx-auto">
                  Ask questions regarding Indian statutory Acts, regulations, definitions, sections, and legal provisions.
                  Responses are strictly evidenced from indexed documents in ChromaDB with verified statutory citations.
                </p>
              </div>

              {/* Sample Prompts */}
              <div className="text-left space-y-2 pt-2">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>Suggested Legal Questions</span>
                </div>
                <div className="grid grid-cols-1 gap-2">
                  {SAMPLE_PROMPTS.map((p, idx) => (
                    <button
                      key={idx}
                      onClick={() => handlePromptClick(p.text)}
                      className="p-3 text-left rounded-xl bg-slate-950/70 border border-slate-800 hover:border-amber-500/40 hover:bg-slate-800/40 text-slate-300 text-xs transition flex items-center justify-between group"
                    >
                      <span className="flex-1">{p.text}</span>
                      <span className="ml-2 text-[10px] bg-slate-800 text-amber-400 px-2 py-0.5 rounded border border-slate-700/60 font-mono">
                        {p.lang}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* Message Stream */
            messages.map((m) => (
              <div key={m.id} className="max-w-3xl mx-auto space-y-3">
                {m.role === 'user' ? (
                  /* User Message */
                  <div className="flex justify-end">
                    <div className="bg-amber-500 text-slate-950 font-medium px-4 py-3 rounded-2xl rounded-tr-sm max-w-xl text-sm shadow-md">
                      {m.content}
                    </div>
                  </div>
                ) : (
                  /* Assistant Message Card */
                  <div className="bg-slate-950/80 border border-slate-800 rounded-2xl p-3 sm:p-5 space-y-4 shadow-xl">
                    {/* Header */}
                    <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                      <div className="flex items-center space-x-2">
                        <div className="w-6 h-6 rounded-md bg-amber-500/10 text-amber-400 flex items-center justify-center">
                          <Scale className="w-3.5 h-3.5" />
                        </div>
                        <span className="text-xs font-bold text-amber-400">
                          NyayaSathi Grounded Legal Finding
                        </span>
                      </div>
                      {m.provider_used && (
                        <div className="text-[10px] text-slate-500 font-mono flex items-center space-x-2">
                          <span>{m.provider_used}</span>
                          {m.processing_time_seconds && (
                            <span>• {m.processing_time_seconds}s</span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Direct Answer Box */}
                    {m.direct_answer && (
                      <div className="bg-slate-900 border-l-4 border-amber-500 p-3.5 rounded-r-xl">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-amber-400 mb-1">
                          Direct Answer
                        </div>
                        <div className="text-sm text-slate-100 font-medium leading-relaxed">
                          {m.direct_answer}
                        </div>
                      </div>
                    )}

                    {/* Legal Explanation */}
                    {m.legal_explanation ? (
                      <div className="space-y-1.5 text-xs text-slate-300 leading-relaxed whitespace-pre-line">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                          Statutory Explanation
                        </div>
                        <div className="text-slate-300">
                          {m.legal_explanation}
                        </div>
                      </div>
                    ) : (
                      <div className="text-xs text-slate-300 leading-relaxed whitespace-pre-line">
                        {m.content}
                      </div>
                    )}

                    {/* Verified Citations */}
                    {m.citations && m.citations.length > 0 && (
                      <div className="space-y-2 pt-1 border-t border-slate-800/60">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                          <FileText className="w-3.5 h-3.5 text-amber-400" />
                          <span>Verified Statutory Sources ({m.citations.length})</span>
                        </div>
                        <div className="grid grid-cols-1 gap-2">
                          {m.citations.map((cite, cIdx) => (
                            <CitationCard key={cIdx} citation={cite} index={cIdx} />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Legal Disclaimer */}
                    <div className="text-[11px] text-slate-500 bg-slate-900/50 p-2.5 rounded-lg border border-slate-800/60 flex items-start space-x-2">
                      <HelpCircle className="w-3.5 h-3.5 text-slate-500 mt-0.5 flex-shrink-0" />
                      <span>{m.disclaimer || 'Information provided for educational purposes only based on indexed official documents. Not formal legal advice.'}</span>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}

          {/* Dynamic Loading State */}
          {loading && (
            <div className="max-w-3xl mx-auto bg-slate-950/80 border border-slate-800 rounded-2xl p-5 space-y-3">
              <div className="flex items-center space-x-3 text-amber-400">
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span className="text-xs font-semibold">
                  {loadingSteps[loadingStep]}
                </span>
              </div>
              <div className="w-full bg-slate-900 rounded-full h-1 overflow-hidden">
                <div className="bg-amber-500 h-1 rounded-full animate-pulse w-3/4"></div>
              </div>
            </div>
          )}

          {/* Error Banner with Retry */}
          {error && (
            <div className="max-w-3xl mx-auto bg-red-950/40 border border-red-800/60 rounded-xl p-4 flex items-start justify-between text-red-200">
              <div className="flex items-start space-x-3">
                <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
                <div className="text-xs">
                  <div className="font-semibold text-red-300">Request Error</div>
                  <div className="mt-0.5 text-red-300/90">{error}</div>
                </div>
              </div>
              {lastFailedQuery && (
                <button
                  onClick={() => handleSendMessage(lastFailedQuery)}
                  className="px-3 py-1 rounded bg-red-800 hover:bg-red-700 text-white text-xs font-medium transition"
                >
                  Retry
                </button>
              )}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <footer className="p-2.5 sm:p-4 border-t border-slate-800 bg-slate-950/80">
          <div className="max-w-3xl mx-auto relative flex items-center space-x-2">
            <textarea
              ref={inputRef}
              rows={1}
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask an Indian legal question in English, Hindi, or Hinglish (e.g. 'What is Section 35?')..."
              disabled={loading}
              className="w-full min-w-0 bg-slate-900 border border-slate-700 rounded-xl pl-3 sm:pl-4 pr-12 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/50 resize-none max-h-32"
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={loading || !inputQuery.trim()}
              className={`absolute right-2.5 p-2 rounded-lg transition ${
                loading || !inputQuery.trim()
                  ? 'text-slate-600 cursor-not-allowed'
                  : 'bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20'
              }`}
              title="Submit legal question (Enter)"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <div className="text-[10px] text-center text-slate-500 mt-2">
            Press <kbd className="bg-slate-900 border border-slate-700 px-1 py-0.5 rounded text-slate-400">Enter</kbd> to send • <kbd className="bg-slate-900 border border-slate-700 px-1 py-0.5 rounded text-slate-400">Shift + Enter</kbd> for new line
          </div>
        </footer>
      </div>
    </div>
  );
}
