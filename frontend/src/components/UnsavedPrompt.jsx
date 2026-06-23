import { useEffect } from 'react';
import { useBlocker } from 'react-router-dom';

export default function UnsavedPrompt({ when, message = 'You have unsaved changes. Are you sure you want to leave?' }) {
  // Block browser back/forward/navigate within app
  const blocker = useBlocker(when);

  useEffect(() => {
    if (blocker.state === 'blocked') {
      const leave = window.confirm(message);
      if (leave) {
        blocker.proceed();
      } else {
        blocker.reset();
      }
    }
  }, [blocker.state]);

  // Block browser close/refresh
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
