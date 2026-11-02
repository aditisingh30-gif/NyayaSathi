/**
 * API Service for Indian Legal & Policy Chatbot backend communication
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export async function fetchHealth() {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status: ${response.status}`);
  }
  return response.json();
}

export async function sendChatMessage(question, conversationId = null, provider = null) {
  const payload = {
    question,
    conversation_id: conversationId,
    provider: provider || undefined,
  };

  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Chat request failed: ${response.statusText}`);
  }

  return response.json();
}

export async function uploadDocument(file, actName = '') {
  const formData = new FormData();
  formData.append('file', file);
  if (actName) {
    formData.append('act_name', actName);
  }

  const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed: ${response.statusText}`);
  }

  return response.json();
}

export async function fetchDocuments() {
  const response = await fetch(`${API_BASE_URL}/api/documents`);
  if (!response.ok) {
    throw new Error(`Failed to load documents: ${response.status}`);
  }
  return response.json();
}

export async function deleteDocument(documentId) {
  const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Failed to delete document: ${response.status}`);
  }
  return response.json();
}

export async function fetchConversations() {
  const response = await fetch(`${API_BASE_URL}/api/conversations`);
  if (!response.ok) {
    throw new Error(`Failed to load conversations: ${response.status}`);
  }
  return response.json();
}

export async function fetchConversation(conversationId) {
  const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}`);
  if (!response.ok) {
    throw new Error(`Failed to load conversation details: ${response.status}`);
  }
  return response.json();
}

export async function deleteConversation(conversationId) {
  const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Failed to delete conversation: ${response.status}`);
  }
  return response.json();
}
