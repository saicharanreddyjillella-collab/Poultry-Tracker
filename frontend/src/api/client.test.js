import { getErrorMessage } from './client';

test('prefers error, then detail, then DRF field errors', () => {
  expect(getErrorMessage({ response: { data: { error: 'Admin only' } } })).toBe('Admin only');
  expect(getErrorMessage({ response: { data: { detail: 'Bill is locked' } } })).toBe('Bill is locked');
  expect(getErrorMessage({ response: { data: { date: ['Bad date'], bird_count: 'Too many' } } }))
    .toBe('Bad date Too many');
});

test('network errors get a friendly message', () => {
  expect(getErrorMessage({})).toBe('Something went wrong. Please try again.');
  expect(getErrorMessage({ response: { data: 'Server down' } })).toBe('Server down');
});
