import { useState, useEffect, useRef } from 'react';

export interface ExplainData {
    function: string;
    file_path: string;
    explanation: string;
    verified: boolean;
    confidence: number;
    verdict: string;
    iterations: number;
    fidelity: number | null;
    codebalance: {
        energy: number;
        debt: number;
        safety: number;
        grade: string;
        details: Record<string, Record<string, string>>;
    };
    critic: {
        factual_pass: boolean;
        completeness_pct: number;
        risks_mentioned: string[];
        issues: string[];
    } | null;
    callers: string[];
    callees: string[];
    context_source: string;
    code_snippet: string;
    timestamp: string;
}

/**
 * Poll /latest_explain.json at a fixed interval.
 * Skips re-render if the timestamp hasn't changed.
 */
export function useLatestExplain(pollInterval = 1000) {
    const [data, setData] = useState<ExplainData | null>(null);
    const [loading, setLoading] = useState(true);
    const lastTimestamp = useRef<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        const fetchData = async () => {
            try {
                const res = await fetch('/latest_explain.json?' + Date.now());
                if (!res.ok) return;                    // file doesn't exist yet
                const json: ExplainData = await res.json();
                if (json.timestamp === lastTimestamp.current) return;  // no change
                lastTimestamp.current = json.timestamp;
                if (!cancelled) {
                    setData(json);
                    setLoading(false);
                }
            } catch {
                // file not ready — silently retry
            }
        };

        fetchData();
        const id = setInterval(fetchData, pollInterval);
        return () => { cancelled = true; clearInterval(id); };
    }, [pollInterval]);

    return { data, loading };
}
