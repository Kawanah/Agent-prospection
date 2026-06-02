import { useState } from 'react';

export function useImportRequest(importRequest) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const run = async (payload) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await importRequest(payload);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur lors de l'import");
    } finally {
      setLoading(false);
    }
  };

  return { loading, result, error, run };
}
