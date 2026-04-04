import { useState, useEffect } from "react";
import { Search, Loader2 } from "lucide-react";
import { searchCases } from "../lib/api";
import { useDebounce } from "../hooks/useDebounce";
import type { CaseResult } from "../types";
import CaseCard from "../components/shared/CaseCard";

export default function CaseViewer() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CaseResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const debouncedQuery = useDebounce(query, 400);

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setResults([]);
      setError(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(false);

    searchCases(debouncedQuery)
      .then((data) => {
        if (!cancelled) setResults(data.results);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [debouncedQuery]);

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <h1 className="text-xl font-bold mb-1">Clinical Cases</h1>
      <p className="text-sm text-content-secondary mb-6">
        Search ~22,000 veterinary cases by symptoms, diagnosis, or species.
      </p>

      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-content-muted" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='e.g. "canine dermatitis pruritus"'
          className="w-full bg-ocean-elevated border border-ocean-border rounded-lg pl-10 pr-4 py-2.5 text-sm text-content-primary placeholder:text-content-muted focus:outline-none focus:border-teal-light"
        />
        {loading && (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-teal" />
        )}
      </div>

      {error && (
        <p className="text-red-400 text-sm mb-4">
          Error searching cases. Check that the backend is running.
        </p>
      )}

      {!loading && debouncedQuery.trim() && results.length === 0 && !error && (
        <p className="text-content-muted text-sm">
          No cases found for &ldquo;{debouncedQuery}&rdquo;
        </p>
      )}

      {!debouncedQuery && (
        <div className="flex-1 flex flex-col items-center justify-center opacity-40 py-20">
          <img src="/logo-white.svg" alt="" className="w-16 h-16 mb-4" />
          <p className="text-content-secondary text-sm">Search 22,000 veterinary cases</p>
        </div>
      )}

      <div className="space-y-3">
        {results.map((result) => (
          <CaseCard key={result.id} result={result} />
        ))}
      </div>
    </div>
  );
}
