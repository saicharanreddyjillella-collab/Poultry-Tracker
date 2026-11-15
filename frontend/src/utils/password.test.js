import { generatePassword } from './password';

test('generated passwords are strong, readable and unique', () => {
  const seen = new Set();
  for (let i = 0; i < 200; i++) {
    const p = generatePassword();
    expect(p).toMatch(/^[A-HJ-NP-Za-hjkmnp-z2-9]{4}-[A-HJ-NP-Za-hjkmnp-z2-9]{4}-[A-HJ-NP-Za-hjkmnp-z2-9]{4}$/);
    expect(p).toMatch(/\d/);            // never all letters
    expect(p).toMatch(/[A-Za-z]/);      // never all digits (server rejects numeric-only)
    expect(p).not.toMatch(/[0O1lI]/);   // no look-alike characters
    seen.add(p);
  }
  expect(seen.size).toBe(200);
});
