// BUG-021: between midnight and 5:30 AM India time the forms used the UTC date
// ("yesterday") as the default and as the latest allowed date.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf, field, istToday } from './helpers';

test.beforeAll(() => reseed());

test('at 1 AM in India, date fields default to today and allow today', async ({ page, request }) => {
  const today = istToday();
  await page.clock.setFixedTime(new Date(`${today}T01:00:00+05:30`));
  const flock = await flockIdOf(request, 'A1');
  await loginAs(page, 'sup_a', `/flocks/${flock}`);
  await page.getByRole('button', { name: '+ Daily Entry' }).click();
  const date = field(page.locator('form.form-card'), 'Date *');
  await expect(date).toHaveValue(today);
  await expect(date).toHaveAttribute('max', today);
});
