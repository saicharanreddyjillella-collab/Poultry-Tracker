/**
 * White-label branding configuration.
 *
 * Every customer-facing name, label, logo and colour is sourced from here so
 * the product can be rebranded for a new company WITHOUT touching feature code.
 *
 * Values come from build-time environment variables (Vite `VITE_BRAND_*`),
 * with sensible defaults. To rebrand: copy `.env.example` to `.env`, fill in
 * the VITE_BRAND_* values, and rebuild (`npm run build`). One `.env` = one
 * customer's branded image.
 */

const env = import.meta.env;

// Helper: pick env value, else fall back to default.
const pick = (key, fallback) => {
  const v = env[key];
  return v === undefined || v === '' ? fallback : v;
};

export const brand = {
  // Company / group — the umbrella name shown on the landing page and titles.
  company:   pick('VITE_BRAND_COMPANY', 'Sai Ram Group'),
  tagline:   pick('VITE_BRAND_TAGLINE', 'Poultry Business Suite'),

  // Per-business display names (used as nav brand + page headings).
  feedsName:   pick('VITE_BRAND_FEEDS_NAME', 'Sai Ram Feeds'),
  chickenName: pick('VITE_BRAND_CHICKEN_NAME', 'Sai Charan Chicken Center'),
  layerName:   pick('VITE_BRAND_LAYER_NAME', 'Sai Ram Layer Farm'),

  // Short names for compact nav back-links.
  feedsShort:   pick('VITE_BRAND_FEEDS_SHORT', 'Feeds'),
  chickenShort: pick('VITE_BRAND_CHICKEN_SHORT', 'Chicken Center'),
  layerShort:   pick('VITE_BRAND_LAYER_SHORT', 'Layer Farm'),

  // Logos — emoji by default; can be a URL to an image via VITE_BRAND_*_LOGO.
  feedsLogo:   pick('VITE_BRAND_FEEDS_LOGO', '🐔'),
  chickenLogo: pick('VITE_BRAND_CHICKEN_LOGO', '🛒'),
  layerLogo:   pick('VITE_BRAND_LAYER_LOGO', '🥚'),

  // Document / bill header details.
  address: pick('VITE_BRAND_ADDRESS', 'Vill. Nagaram, Mdl. Lingalaghanpur, Dist. Jangaon - 506 167'),
  phone:   pick('VITE_BRAND_PHONE', ''),
  email:   pick('VITE_BRAND_EMAIL', ''),
  gstin:   pick('VITE_BRAND_GSTIN', ''),

  // Which business name the bill/settlement header should carry.
  billName: pick('VITE_BRAND_BILL_NAME', pick('VITE_BRAND_FEEDS_NAME', 'Sai Ram Feeds')),

  // Theme colour (applied as CSS variable --brand-primary).
  primaryColor: pick('VITE_BRAND_PRIMARY_COLOR', ''),

  // Browser tab title + PWA name.
  appTitle: pick('VITE_BRAND_APP_TITLE', pick('VITE_BRAND_FEEDS_NAME', 'Sai Ram Feeds')),
  faviconUrl: pick('VITE_BRAND_FAVICON_URL', ''),
};

/**
 * Apply runtime branding to the document: title, PWA meta, optional theme
 * colour and favicon. Call once at app start.
 */
export function applyBrand() {
  try {
    if (brand.appTitle) document.title = brand.appTitle;

    const pwa = document.querySelector('meta[name="apple-mobile-web-app-title"]');
    if (pwa && brand.appTitle) pwa.setAttribute('content', brand.appTitle);

    if (brand.primaryColor) {
      document.documentElement.style.setProperty('--brand-primary', brand.primaryColor);
    }
    if (brand.faviconUrl) {
      let link = document.querySelector('link[rel="icon"]');
      if (!link) {
        link = document.createElement('link');
        link.rel = 'icon';
        document.head.appendChild(link);
      }
      link.href = brand.faviconUrl;
    }
  } catch (e) {
    // Non-fatal: branding is cosmetic.
    console.warn('applyBrand failed', e);
  }
}

export default brand;
