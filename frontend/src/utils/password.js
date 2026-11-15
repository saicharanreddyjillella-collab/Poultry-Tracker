// Strong, easy-to-read temporary passwords (no 0/O, 1/l/I) — e.g. "Kp7m-Qx4t-Rw9a".
const CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';

export function generatePassword() {
  const bytes = new Uint32Array(12);
  crypto.getRandomValues(bytes);
  const c = Array.from(bytes, b => CHARS[b % CHARS.length]);
  // Guarantee a digit and a letter so it always passes the server's policy.
  c[3] = '23456789'[bytes[3] % 8];
  c[4] = 'ABCDEFGHJKMNPQRSTUVWXYZ'[bytes[4] % 23];
  return `${c.slice(0, 4).join('')}-${c.slice(4, 8).join('')}-${c.slice(8).join('')}`;
}

export const PASSWORD_HINT = 'At least 8 characters, not only numbers, and not a common password.';
