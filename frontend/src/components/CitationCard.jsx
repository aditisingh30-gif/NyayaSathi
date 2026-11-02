import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp, FileText, Bookmark, ExternalLink } from 'lucide-react';

export default function CitationCard({ citation, index }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border border-slate-700/80 bg-slate-900/90 rounded-xl overflow-hidden text-xs transition hover:border-amber-500/50">
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="px-3 py-2.5 flex items-center justify-between cursor-pointer hover:bg-slate-800/60 transition"
      >
        <div className="flex items-center space-x-2 flex-wrap gap-y-1">
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-medium">
            <Bookmark className="w-3 h-3 text-amber-400" />
            <span>Citation {index + 1}</span>
          </span>

          <span className="font-semibold text-slate-200">
            {citation.act_name || 'Indian Statute'}
          </span>

          {citation.section && (
            <span className="px-2 py-0.5 rounded bg-slate-800 text-amber-400 border border-slate-700 font-mono">
              {citation.section}
            </span>
          )}

          {citation.page_number && (
            <span className="text-slate-400 font-mono">
              Page {citation.page_number}
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2 text-slate-400">
          <span className="text-[11px] hidden sm:inline">
            {isExpanded ? 'Hide Excerpt' : 'View Excerpt'}
          </span>
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </div>

      {isExpanded && (
        <div className="px-3.5 py-3 border-t border-slate-800/90 bg-slate-950/70 text-slate-300 space-y-2">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span className="flex items-center space-x-1">
              <FileText className="w-3.5 h-3.5 text-slate-500" />
              <span>Source: <code className="text-slate-300 font-mono">{citation.document_name}</code></span>
            </span>
            {citation.relevance_score && (
              <span className="font-mono text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-900/40">
                Score: {(citation.relevance_score * 100).toFixed(0)}%
              </span>
            )}
          </div>

          <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800 font-serif text-[12px] leading-relaxed text-slate-200 italic">
            "{citation.snippet}"
          </div>
        </div>
      )}
    </div>
  );
}
