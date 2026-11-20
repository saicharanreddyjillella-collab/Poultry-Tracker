import { useSearchParams } from 'react-router-dom';

/** ?scope= in the address: undefined lets the server pick (supervisors: their regions). */
export function useScope() {
  const [params, setParams] = useSearchParams();
  const scope = params.get('scope') || undefined;
  const setScope = (v) => {
    const next = new URLSearchParams(params);
    next.set('scope', v);
    setParams(next, { replace: true });
  };
  return [scope, setScope];
}
