/**
 * <<< INTEGRATION: replaced mock setInterval with real EventSource >>>
 *
 * EventSource cannot set custom headers, so the JWT is passed as
 * ?token=<jwt> query param.  The backend SSE endpoint accepts both
 * Authorization: Bearer (API clients) and ?token= (browser EventSource).
 *
 * Events received from the backend:
 *   event: "message"  data: { event: "transaction.created" | "transaction.deleted" | "transaction.updated", data: {...} }
 *   event: "ping"     data: "keep-alive"   (heartbeat — ignored)
 *
 * On each transaction event the relevant TanStack Query cache keys are
 * invalidated so all components re-fetch automatically.
 */

import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { tokenStorage } from '../lib/api';

interface SSEPayload {
  event: string;
  data: unknown;
  timestamp: string;
}

const QUERY_KEYS_BY_EVENT: Record<string, string[][]> = {
  'transaction.created': [['transactions']],
  'transaction.updated': [['transactions']],
  'transaction.deleted': [['transactions']],
};

export function useSSE(path: string) {
  const queryClient = useQueryClient();
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const token = tokenStorage.get();
    if (!token) return; // not authenticated — skip

    // <<< INTEGRATION: ?token= query param auth (EventSource limitation) >>>
    const base = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
    const url = `${base}${path}?token=${encodeURIComponent(token)}`;

    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener('message', (e: MessageEvent) => {
      try {
        const payload: SSEPayload = JSON.parse(e.data as string);
        const keys = QUERY_KEYS_BY_EVENT[payload.event];
        if (keys) {
          keys.forEach((key) =>
            queryClient.invalidateQueries({ queryKey: key }),
          );
        }
      } catch {
        // malformed event — ignore
      }
    });

    es.addEventListener('ping', () => {
      // heartbeat — no action needed
    });

    es.onerror = () => {
      // EventSource auto-reconnects on transient errors.
      // On persistent failure (e.g. 401) the browser stops retrying after
      // readyState === CLOSED.  We rely on the 401 handler in api.ts to
      // redirect the user to login.
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [path, queryClient]);
}
