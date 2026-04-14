import { useState, useCallback } from "react";
import { resolveEntity } from "../api/deallens.js";

export function useCompanySearch() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const search = useCallback(async (query, queryType = "auto", jurisdictionHint = null) => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await resolveEntity(query, queryType, jurisdictionHint);
      setResult(data);
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { result, loading, error, search, reset };
}
