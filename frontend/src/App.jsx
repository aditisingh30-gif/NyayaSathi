import React, { useState, useEffect } from 'react';
import {
  Scale,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  MessageSquare,
  FileText,
  Database,
  Layers,
  Sparkles,
  Bot
} from 'lucide-react';
import { fetchHealth } from './services/api';
import DocumentManager from './components/DocumentManager';
import ChatInterface from './components/ChatInterface';

export default function App() {
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' | 'documents' | 'system'
  const [healthStatus, setHealthStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const checkBackendHealth = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchHealth();
      setHealthStatus(data);
    } catch (err) {
      setError(err.message || 'Unable to connect to backend service.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkBackendHealth();
  }, []);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-500">
              <Scale className="w-6 h-6" />
            </div>
            <div>
              <span className="font-bold text-lg text-amber-400">NyayaSathi</span>
              <span className="ml-2 text-xs text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                Indian Legal Assistant
              </span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center space-x-2 bg-slate-900 border border-slate-800 p-1 rounded-lg">
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition ${
                activeTab === 'chat'
                  ? 'bg-amber-500 text-slate-950 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Bot className="w-3.5 h-3.5" />
              <span>Legal Chat</span>
            </button>

            <button
              onClick={() => setActiveTab('documents')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition ${
                activeTab === 'documents'
                  ? 'bg-amber-500 text-slate-950 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Document Ingestion</span>
              <span className="text-[10px] bg-slate-950/30 px-1.5 py-0.2 rounded font-mono">ChromaDB</span>
            </button>

            <button
              onClick={() => setActiveTab('system')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition ${
                activeTab === 'system'
                  ? 'bg-amber-500 text-slate-950 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Database className="w-3.5 h-3.5" />
              <span>Architecture</span>
            </button>
          </div>

          <div className="flex items-center space-x-4">
            <button
              onClick={checkBackendHealth}
              disabled={loading}
              className="text-xs flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
              title="Refresh backend status"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Verify Health</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Workspace Area */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 flex flex-col">
        {activeTab === 'chat' ? (
          <ChatInterface />
        ) : activeTab === 'documents' ? (
          <DocumentManager />
        ) : (
          <div className="max-w-3xl w-full mx-auto text-center space-y-6 my-auto py-6">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Full RAG Pipeline Active • Stages 1-5 Operational</span>
            </div>

            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
              AI-Based Indian Legal & Policy Information Assistant
            </h1>

            <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
              A reliable, grounded RAG assistant built for Indian Acts, regulations, and policy documents.
              Designed for transparent answers, direct statutory citations, and multi-lingual query understanding (English, Hindi, and Hinglish).
            </p>

            {/* Service Status Card */}
            <div className="mt-8 bg-slate-950/60 border border-slate-800 rounded-xl p-6 text-left shadow-xl">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-4">
                System Health & Architecture Status
              </h2>

              {loading ? (
                <div className="flex items-center space-x-3 text-slate-400 py-3">
                  <RefreshCw className="w-5 h-5 animate-spin text-amber-400" />
                  <span>Checking backend connection at http://127.0.0.1:8000/health...</span>
                </div>
              ) : error ? (
                <div className="bg-red-950/40 border border-red-800/50 rounded-lg p-4 flex items-start space-x-3 text-red-300">
                  <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="font-semibold text-sm">Backend Not Reachable</div>
                    <div className="text-xs text-red-400 mt-1">{error}</div>
                    <div className="text-xs text-slate-400 mt-2">
                      Ensure the FastAPI backend is running via <code className="bg-slate-900 px-1 py-0.5 rounded text-amber-300">uvicorn app.main:app</code> on port 8000.
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="bg-emerald-950/30 border border-emerald-800/40 rounded-lg p-4 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                      <div>
                        <div className="font-semibold text-sm text-emerald-200">FastAPI Backend Operational</div>
                        <div className="text-xs text-emerald-400/80">
                          {healthStatus.app_name} (v{healthStatus.version}) • Environment: {healthStatus.environment}
                        </div>
                      </div>
                    </div>
                    <span className="text-xs font-mono bg-emerald-900/60 text-emerald-300 px-2.5 py-1 rounded-full border border-emerald-700/50">
                      HTTP 200 OK
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                    <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3 text-center">
                      <div className="text-xs text-slate-400">Frontend Stack</div>
                      <div className="text-sm font-semibold text-slate-200 mt-1">React 18 + Vite + Tailwind</div>
                    </div>
                    <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3 text-center">
                      <div className="text-xs text-slate-400">Backend API</div>
                      <div className="text-sm font-semibold text-slate-200 mt-1">FastAPI + Uvicorn + Pydantic</div>
                    </div>
                    <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3 text-center">
                      <div className="text-xs text-slate-400">RAG Engine</div>
                      <div className="text-sm font-semibold text-slate-200 mt-1">PyMuPDF + ChromaDB + MiniLM</div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Development Roadmap Stage Indicators */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-left pt-2">
              <div className="p-4 rounded-lg border border-emerald-800/50 bg-emerald-950/10">
                <div className="flex items-center space-x-2 text-emerald-400 text-sm font-semibold mb-1">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Stage 2: Ingestion</span>
                </div>
                <p className="text-xs text-slate-400">
                  40-page Consumer Protection Act, 2019 indexed into 157 statutory chunks in ChromaDB.
                </p>
              </div>

              <div className="p-4 rounded-lg border border-emerald-800/50 bg-emerald-950/10">
                <div className="flex items-center space-x-2 text-emerald-400 text-sm font-semibold mb-1">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Stage 3: Retrieval</span>
                </div>
                <p className="text-xs text-slate-400">
                  Multilingual Hindi/Hinglish query processing, hybrid scoring, exact section boosting, and thresholding.
                </p>
              </div>

              <div className="p-4 rounded-lg border border-emerald-800/50 bg-emerald-950/10">
                <div className="flex items-center space-x-2 text-emerald-400 text-sm font-semibold mb-1">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Stage 4: Grounded AI</span>
                </div>
                <p className="text-xs text-slate-400">
                  Modular providers (Gemini/OpenAI/Ollama/Synthesizer), citation verification, and session persistence.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-3 text-center text-xs text-slate-500">
        <p>Indian Legal Information Assistant • Educational & Research Information System • Not Legal Advice</p>
      </footer>
    </div>
  );
}
