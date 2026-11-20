import { useRef, useState } from 'react';

/** The server's "outside the edit window — give a reason" answer, or null. */
export function approvalMessage(err) {
  const d = err?.response?.status === 400 ? err.response.data : null;
  const m = d?.change_reason;
  return m ? (Array.isArray(m) ? m[0] : String(m)) : null;
}

/** run(call): call(extra) once; if the date is outside the edit window, ask for a reason and
 *  call(extra + change_reason) again. Resolves to { pending: true } when it went for approval,
 *  { cancelled: true } when the person cancelled, or { response } when saved straight away. */
export default function useApprovalSave() {
  const [ask, setAsk] = useState({ open: false, message: '' });
  const resolver = useRef(null);

  const askReason = (message) => new Promise(resolve => {
    resolver.current = resolve;
    setAsk({ open: true, message });
  });
  const close = (value) => { setAsk({ open: false, message: '' }); resolver.current?.(value); };

  const run = async (call) => {
    try {
      const response = await call({});
      return response?.status === 202 ? { pending: true } : { response };
    } catch (err) {
      const message = approvalMessage(err);
      if (!message) throw err;
      const reason = await askReason(message);
      if (!reason) return { cancelled: true };
      const response = await call({ change_reason: reason });
      return response?.status === 202 ? { pending: true } : { response };
    }
  };

  return { run, dialogProps: { open: ask.open, message: ask.message, onSubmit: close, onCancel: () => close(null) } };
}
