import React, { useState, useEffect } from 'react';
import {
  FileText,
  Upload,
  Trash2,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Database,
  Layers,
  BookOpen,
  Hash,
  ShieldCheck,
  FileCheck
} from 'lucide-react';
import { fetchDocuments, uploadDocument, deleteDocument } from '../services/api';

export default function DocumentManager() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Form state
  const [selectedFile, setSelectedFile] = useState(null);
  const [actName, setActName] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const docs = await fetchDocuments();
      setDocuments(docs || []);
    } catch (err) {
      setError(err.message || 'Failed to retrieve indexed documents.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setError('Only PDF files are supported. Please select an authentic legal PDF document.');
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
      setError(null);
      setSuccess(null);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setError('Only PDF files are supported.');
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
      setError(null);
      setSuccess(null);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select a PDF document to upload.');
      return;
    }

    try {
      setUploading(true);
      setError(null);
      setSuccess(null);

      const response = await uploadDocument(selectedFile, actName.trim());
      setSuccess(
        response.message ||
        `Successfully indexed ${response.document?.act_name || 'document'} (${response.document?.total_chunks} statutory chunks).`
      );

      // Reset form
      setSelectedFile(null);
      setActName('');
      // Reload documents list
      await loadDocuments();
    } catch (err) {
      setError(err.message || 'Ingestion pipeline error occurred.');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId) => {
    try {
      setDeletingId(docId);
      setError(null);
      await deleteDocument(docId);
      setSuccess(`Document '${docId}' removed from vector index.`);
      setDeleteConfirmId(null);
      await loadDocuments();
    } catch (err) {
      setError(err.message || 'Failed to remove document from index.');
    } finally {
      setDeletingId(null);
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const totalChunks = documents.reduce((sum, d) => sum + (d.total_chunks || 0), 0);
  const totalPages = documents.reduce((sum, d) => sum + (d.total_pages || 0), 0);

  return (
    <div className="w-full space-y-8">
      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 flex items-center space-x-4">
          <div className="w-12 h-12 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-white">{documents.length}</div>
            <div className="text-xs text-slate-400">Indexed Acts & Policies</div>
          </div>
        </div>

        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 flex items-center space-x-4">
          <div className="w-12 h-12 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-white">{totalChunks}</div>
            <div className="text-xs text-slate-400">Statutory Chunks</div>
          </div>
        </div>

        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 flex items-center space-x-4">
          <div className="w-12 h-12 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <div className="text-2xl font-bold text-white">{totalPages} Pages</div>
            <div className="text-xs text-slate-400">ChromaDB Vector Store</div>
          </div>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="bg-red-950/40 border border-red-800/60 rounded-xl p-4 flex items-start space-x-3 text-red-200">
          <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1 text-sm">
            <div className="font-semibold text-red-300">Ingestion Error</div>
            <div className="text-red-300/90 mt-1 whitespace-pre-wrap">{error}</div>
          </div>
        </div>
      )}

      {success && (
        <div className="bg-emerald-950/40 border border-emerald-800/60 rounded-xl p-4 flex items-start space-x-3 text-emerald-200">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1 text-sm">
            <div className="font-semibold text-emerald-300">Success</div>
            <div className="text-emerald-300/90 mt-1">{success}</div>
          </div>
        </div>
      )}

      {/* Upload Section */}
      <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center space-x-2">
              <Upload className="w-5 h-5 text-amber-400" />
              <span>Ingest Indian Legal Act / Regulation (PDF)</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Extracts text via PyMuPDF, cleans formatting, preserves Act/Section statutory boundaries, and indexes 384-dimensional dense vectors into ChromaDB.
            </p>
          </div>
        </div>

        <form onSubmit={handleUpload} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Act / Policy Title (Optional Override)
              </label>
              <input
                type="text"
                value={actName}
                onChange={(e) => setActName(e.target.value)}
                placeholder="e.g. The Consumer Protection Act, 2019"
                className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3.5 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500/80 focus:ring-1 focus:ring-amber-500/50"
              />
              <span className="text-[11px] text-slate-500 mt-1 block">
                If left blank, the system will detect the Act title automatically from the first page text.
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Embedding Model
              </label>
              <div className="w-full bg-slate-900 border border-slate-700/50 rounded-lg px-3.5 py-2 text-xs text-slate-400 flex items-center justify-between">
                <span>all-MiniLM-L6-v2</span>
                <span className="text-[10px] bg-slate-800 text-amber-400 px-2 py-0.5 rounded font-mono">384-d</span>
              </div>
            </div>
          </div>

          {/* Drag & Drop Area */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-6 text-center transition-all ${
              isDragging
                ? 'border-amber-400 bg-amber-500/5'
                : selectedFile
                ? 'border-emerald-500/50 bg-emerald-950/10'
                : 'border-slate-800 hover:border-slate-700 bg-slate-900/40'
            }`}
          >
            <input
              type="file"
              accept=".pdf,application/pdf"
              id="legal-pdf-upload"
              onChange={handleFileChange}
              className="hidden"
            />
            <label
              htmlFor="legal-pdf-upload"
              className="cursor-pointer flex flex-col items-center justify-center space-y-2"
            >
              {selectedFile ? (
                <>
                  <div className="w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
                    <FileCheck className="w-6 h-6" />
                  </div>
                  <div className="text-sm font-semibold text-emerald-300">{selectedFile.name}</div>
                  <div className="text-xs text-slate-400">{formatFileSize(selectedFile.size)} • PDF Ready for Ingestion</div>
                  <span className="text-xs text-amber-400 underline pt-1">Click to change file</span>
                </>
              ) : (
                <>
                  <div className="w-12 h-12 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center">
                    <Upload className="w-6 h-6" />
                  </div>
                  <div className="text-sm font-medium text-slate-300">
                    <span className="text-amber-400 underline">Click to upload</span> or drag and drop official legal PDF
                  </div>
                  <div className="text-xs text-slate-500">Maximum file size: 50MB • PDF format only</div>
                </>
              )}
            </label>
          </div>

          <div className="flex justify-end pt-1">
            <button
              type="submit"
              disabled={uploading || !selectedFile}
              className={`px-5 py-2.5 rounded-lg text-sm font-semibold flex items-center space-x-2 transition ${
                uploading || !selectedFile
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50'
                  : 'bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-lg shadow-amber-500/20'
              }`}
            >
              {uploading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Processing & Ingesting Chunks...</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  <span>Validate & Ingest Document</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Indexed Documents Table */}
      <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center space-x-2">
              <Database className="w-5 h-5 text-emerald-400" />
              <span>Indexed Legal Documents in ChromaDB</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Statutory documents available for semantic retrieval in upcoming Stage 3.
            </p>
          </div>
          <button
            onClick={loadDocuments}
            disabled={loading}
            className="text-xs flex items-center space-x-1 px-3 py-1.5 rounded-md bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {loading && documents.length === 0 ? (
          <div className="text-center py-12 text-slate-400 space-y-2">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-amber-400" />
            <p className="text-sm">Loading indexed legal documents...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-12 text-slate-500 space-y-3">
            <BookOpen className="w-10 h-10 mx-auto text-slate-600" />
            <p className="text-sm text-slate-400">No legal documents indexed yet.</p>
            <p className="text-xs text-slate-500">
              Upload an authentic PDF above (e.g. Consumer Protection Act, 2019) to begin.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="text-xs uppercase bg-slate-900/80 text-slate-400 border-b border-slate-800">
                <tr>
                  <th scope="col" className="px-4 py-3 rounded-l-lg">Act / Policy Name</th>
                  <th scope="col" className="px-4 py-3">File Name</th>
                  <th scope="col" className="px-4 py-3 text-center">Pages</th>
                  <th scope="col" className="px-4 py-3 text-center">Chunks</th>
                  <th scope="col" className="px-4 py-3">Status</th>
                  <th scope="col" className="px-4 py-3 text-right rounded-r-lg">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {documents.map((doc) => (
                  <tr key={doc.document_id} className="hover:bg-slate-900/40 transition">
                    <td className="px-4 py-3.5">
                      <div className="font-semibold text-slate-100 flex items-center space-x-2">
                        <FileText className="w-4 h-4 text-amber-400 flex-shrink-0" />
                        <span>{doc.act_name}</span>
                      </div>
                      <div className="text-[11px] font-mono text-slate-500 mt-0.5">
                        ID: {doc.document_id}
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="text-xs text-slate-300 truncate max-w-xs">{doc.filename}</div>
                      <div className="text-[11px] text-slate-500">{formatFileSize(doc.file_size_bytes)}</div>
                    </td>
                    <td className="px-4 py-3.5 text-center text-xs font-mono text-slate-300">
                      {doc.total_pages}
                    </td>
                    <td className="px-4 py-3.5 text-center">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20 font-mono">
                        {doc.total_chunks}
                      </span>
                    </td>
                    <td className="px-4 py-3.5">
                      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-800/50">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Indexed</span>
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      {deleteConfirmId === doc.document_id ? (
                        <div className="inline-flex items-center space-x-2">
                          <span className="text-[11px] text-red-400">Confirm?</span>
                          <button
                            onClick={() => handleDelete(doc.document_id)}
                            disabled={deletingId === doc.document_id}
                            className="px-2 py-1 rounded bg-red-600 hover:bg-red-500 text-white text-xs font-medium transition"
                          >
                            {deletingId === doc.document_id ? 'Deleting...' : 'Yes, Delete'}
                          </button>
                          <button
                            onClick={() => setDeleteConfirmId(null)}
                            className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setDeleteConfirmId(doc.document_id)}
                          className="p-1.5 rounded-md hover:bg-red-500/10 text-slate-400 hover:text-red-400 transition"
                          title="Delete from vector index (preserves original PDF)"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
