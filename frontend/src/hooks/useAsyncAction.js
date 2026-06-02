import { useCallback, useState } from 'react';
import { getErrorMessage } from '../lib/api';

export function useAsyncAction({ fallbackError = 'Action impossible' } = {}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = useCallback(
    async (action) => {
      setLoading(true);
      setError(null);
      try {
        return await action();
      } catch (err) {
        const message = getErrorMessage(err, fallbackError);
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [fallbackError]
  );

  return { loading, error, setError, run };
}
