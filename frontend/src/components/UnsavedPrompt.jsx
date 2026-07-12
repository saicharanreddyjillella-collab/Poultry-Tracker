import { useEffect } from 'react';

export default function UnsavedPrompt({ when, message = 'You have unsaved changes. Are you sure you want to leave?' }) {
  // Block browser close/refresh only
  useEffect(() => {
    const handler = (e) => {
      if (when) {
        e.preventDefault();
        e.returnValue = message;
        return message;
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [when, message]);

  return null;
}
