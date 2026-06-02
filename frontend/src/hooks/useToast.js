import { useCallback, useEffect, useState } from 'react';

export function useToast(timeout = 3000) {
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(() => setToast(null), timeout);
    return () => clearTimeout(timer);
  }, [toast, timeout]);

  const showToast = useCallback((message, color = 'green') => {
    setToast({ msg: message, color, message });
  }, []);

  const clearToast = useCallback(() => setToast(null), []);

  return { toast, showToast, clearToast };
}
