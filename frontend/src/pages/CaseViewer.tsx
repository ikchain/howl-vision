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
      <p className="text-sm text-gray-400 mb-6">
        Search ~22,000 veterinary cases by symptoms, diagnosis, or species.
      </p>

      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='e.g. "canine dermatitis pruritus"'
          className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-2.5 text-sm text-gray-100 placeholder:text-gray-500 focus:outline-none focus:border-emerald-500"
        />
        {loading && (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 animate-spin" />
        )}
      </div>

      {error && (
        <p className="text-red-400 text-sm mb-4">
          Error searching cases. Check that the backend is running.
        </p>
      )}

      {!loading && debouncedQuery.trim() && results.length === 0 && !error && (
        <p className="text-gray-500 text-sm">
          No cases found for &ldquo;{debouncedQuery}&rdquo;
        </p>
      )}

      <div className="space-y-3">
        {results.map((result) => (
          <CaseCard key={result.id} result={result} />
        ))}
      </div>
    </div>
  );
}
