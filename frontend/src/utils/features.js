// Which optional features are switched on (admin: Settings → Features).
// Loaded once per page load and shared; refreshFeatures() after a change.
import { useEffect, useSyncExternalStore } from 'react';
import { featureAPI } from '../api/client';

let state = { loaded: false, on: {} };
let inflight = null;
const listeners = new Set();
const emit = () => listeners.forEach(l => l());

export function refreshFeatures() {
  inflight = featureAPI.states()
    .then(r => { state = { loaded: true, on: r.data || {} }; })
    .catch(() => { state = { loaded: true, on: state.on }; })
    .finally(() => { inflight = null; emit(); });
  return inflight;
}

export function setFeatureLocally(key, enabled) {
  state = { loaded: true, on: { ...state.on, [key]: enabled } };
  emit();
}

/** { loaded, isOn(key) } — a feature counts as on until the switches have loaded and say otherwise. */
export function useFeatures() {
  const snap = useSyncExternalStore(cb => { listeners.add(cb); return () => listeners.delete(cb); }, () => state);
  useEffect(() => { if (!snap.loaded && !inflight) refreshFeatures(); }, [snap.loaded]);
  return { loaded: snap.loaded, isOn: (key) => snap.on[key] !== false };
}
