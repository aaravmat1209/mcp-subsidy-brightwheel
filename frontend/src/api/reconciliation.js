/**
 * API client for reconciliation backend
 * Connects to FastAPI backend running Python orchestrator
 */

const API_BASE = 'http://localhost:8000/api';

export const uploadFile = async (file, workflow) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('workflow', workflow);

  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }

  return response.json();
};

export const startReconciliation = async (fileIds) => {
  const response = await fetch(`${API_BASE}/reconcile`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(fileIds),
  });

  if (!response.ok) {
    throw new Error(`Reconciliation failed: ${response.statusText}`);
  }

  return response.json();
};

export const getJobStatus = async (jobId) => {
  const response = await fetch(`${API_BASE}/job/${jobId}`);

  if (!response.ok) {
    throw new Error(`Failed to get job status: ${response.statusText}`);
  }

  return response.json();
};

export const streamJobProgress = (jobId, onUpdate, onComplete, onError) => {
  const eventSource = new EventSource(`${API_BASE}/job/${jobId}/stream`);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      console.log('[SSE] Received update:', {
        stage: data.stage,
        progress: data.progress,
        tool_calls_count: data.tool_calls?.length || 0
      });

      if (data.error) {
        onError(data.error);
        eventSource.close();
        return;
      }

      onUpdate(data);

      if (data.status === 'complete') {
        onComplete(data.results);
        eventSource.close();
      } else if (data.status === 'failed') {
        onError(data.error || 'Job failed');
        eventSource.close();
      }
    } catch (err) {
      onError(err.message);
      eventSource.close();
    }
  };

  eventSource.onerror = (error) => {
    console.error('[SSE] Connection error:', error);
    onError('Backend connection lost. Please restart the backend server.');
    eventSource.close();
  };

  return () => eventSource.close();
};
