// A supervisor's bill waits for the admin; the admin approves it and records payments.
import { test, expect } from '@playwright/test';
import { reseed, loginAs, flockIdOf } from './helpers';

test.describe.configure({ mode: 'serial' });
test.beforeAll(() => reseed());

let flock;
const money = (s) => Number(s.replace(/[₹,\s]/g, ''));

test('a supervisor\'s bill waits for approval', async ({ page, request }) => {
  flock = await flockIdOf(request, 'A3');
  await loginAs(page, 'sup_a', `/flocks/${flock}`);
  await page.getByRole('button', { name: 'Close & Generate Bill' }).click();
  await page.getByRole('button', { name: 'Generate Bill', exact: true }).click();
  const box = page.getByRole('region', { name: 'Approval and payments' });
  await expect(box).toContainText('Waiting for approval');
  await expect(box.getByRole('button', { name: 'Approve bill' })).toHaveCount(0);
});

test('the admin approves it from Approvals and records a part payment, then the rest', async ({ page }) => {
  await loginAs(page, 'admin', '/approvals');
  const waiting = page.getByRole('region', { name: 'Bills waiting for approval' });
  await expect(waiting).toContainText('Krishna Farm');
  await waiting.getByRole('link', { name: 'Open bill' }).click();
  const box = page.getByRole('region', { name: 'Approval and payments' });
  await box.getByRole('button', { name: 'Approve bill' }).click();
  await expect(box).toContainText('Approved by');
  await expect(box).toContainText('Unpaid');
  const toPay = money(await box.locator('dt:has-text("To pay") + dd').innerText());

  await box.getByRole('button', { name: '+ Record payment' }).click();
  const form = box.getByRole('form', { name: 'Record payment' });
  await expect(form.getByLabel('Amount (₹) *')).toHaveValue(String(toPay));       // balance pre-filled
  await form.getByLabel('Amount (₹) *').fill('10000');
  await form.getByLabel('Mode').selectOption('upi');
  await form.getByLabel('UTR / reference').fill('UPI-4471');
  await form.getByRole('button', { name: 'Save payment' }).click();
  await expect(box).toContainText('Part paid');
  await expect(box.locator('tbody tr')).toContainText('UPI-4471');
  expect(money(await box.locator('dt:has-text("Balance due") + dd').innerText())).toBeCloseTo(toPay - 10000, 2);

  await box.getByRole('button', { name: '+ Record payment' }).click();
  await box.getByRole('form', { name: 'Record payment' }).getByRole('button', { name: 'Save payment' }).click();
  await expect(box).toContainText('Paid');
  await expect(box.getByRole('button', { name: '+ Record payment' })).toHaveCount(0);
  await page.goto('/approvals');
  await expect(page.getByText('Every approved bill is paid.')).toBeVisible();
});

test('the supervisor sees the payments but cannot change them', async ({ page }) => {
  await loginAs(page, 'sup_a', `/flocks/${flock}/bill`);
  const box = page.getByRole('region', { name: 'Approval and payments' });
  await expect(box).toContainText('UPI-4471');
  await expect(box.getByRole('button', { name: /Remove payment/ })).toHaveCount(0);
});
