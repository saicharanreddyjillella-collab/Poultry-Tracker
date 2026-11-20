import { useEffect, useState } from 'react';
import { feedTypeAPI } from '../api/client';

// One fetch per page load, shared by every screen; reload() after the admin edits the list.
let cache = null;
let pending = null;
const listeners = new Set();

function load(force = false) {
  if (cache && !force) return Promise.resolve(cache);
  if (!pending || force) {
    pending = feedTypeAPI.list().then(r => { cache = r.data; pending = null; listeners.forEach(fn => fn(cache)); return cache; })
      .catch(() => { pending = null; return cache || []; });
  }
  return pending;
}

/** The admin's feed types (Settings → Feed types), in feeding order.
 *  Records store a permanent `key`; show `code(key)` to people. */
export default function useFeedTypes() {
  const [types, setTypes] = useState(cache || []);
  useEffect(() => {
    listeners.add(setTypes);
    load().then(setTypes);
    return () => listeners.delete(setTypes);
  }, []);
  const byKey = Object.fromEntries(types.map(t => [t.key, t]));
  return {
    types,
    active: types.filter(t => t.active),
    byKey,
    code: (key) => byKey[key]?.code || key,
    colour: (key) => byKey[key]?.colour || '#546679',
    reload: () => load(true),
  };
}
