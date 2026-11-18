import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, test, expect } from 'vitest';
import HeatBanner from './HeatBanner';

const { summary } = vi.hoisted(() => ({ summary: { current: null } }));
vi.mock('../api/client', () => ({
  insightsAPI: { heatStress: () => Promise.resolve({ data: { summary: summary.current } }) },
}));
const show = () => render(<MemoryRouter><HeatBanner /></MemoryRouter>);

test('warns about farms at danger or worse, with emergency count', async () => {
  summary.current = { at_risk_next_3_days: 3, emergency_next_3_days: 1 };
  show();
  expect(await screen.findByRole('status')).toHaveTextContent('3 farms at danger level or worse in the next 3 days (1 at emergency)');
  expect(screen.getByRole('link', { name: /See what to do/ })).toHaveAttribute('href', '/heat-stress');
});

test('one farm, no emergency', async () => {
  summary.current = { at_risk_next_3_days: 1, emergency_next_3_days: 0 };
  show();
  expect(await screen.findByRole('status')).toHaveTextContent(/1 farm at danger level or worse in the next 3 days\.$|1 farm at danger level or worse in the next 3 days\. /);
});

test('nothing shown when there is no risk', async () => {
  summary.current = { at_risk_next_3_days: 0, emergency_next_3_days: 0 };
  const { container } = show();
  await new Promise(r => setTimeout(r, 20));
  expect(container).toBeEmptyDOMElement();
});
