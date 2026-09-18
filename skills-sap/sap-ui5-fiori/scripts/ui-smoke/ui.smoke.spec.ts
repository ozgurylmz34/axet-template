import { test, expect } from '@playwright/test';

// Jenerik render smoke — herhangi bir freestyle UI5 + OData V2 uygulaması için (SMOKE_BASE_URL ile seçilir).
// Yakalar: render çökmesi (ör. VBox içinde core:Title), routing hedef çökmesi, undefined hataları,
// $metadata 401 (kimlik kopuk), boş sayfa. Uygulamaya özel akış (oluştur/kaydet) için bu dosya KOPYALANIP genişletilir.

// Build edilmemiş geliştirme modunun NORMAL gürültüsü — gerçek hata değil.
const IGNORE = [
  'Component-preload.js',
  'i18n_tr.properties',
  'favicon.ico',
  'unload is not allowed',
  'Failed to load resource: the server responded with a status of 404',
  'is not contained in the list of supported locales',
  'fallback locale',
];

function isReal(msg: string): boolean {
  return !IGNORE.some((s) => msg.includes(s));
}

test('render smoke — gerçek console error yok + $metadata 200 + sayfa doldu', async ({ page }) => {
  const errors: string[] = [];
  let metaStatus = -1;

  page.on('console', (m) => {
    if (m.type() === 'error' && isReal(m.text())) errors.push(m.text());
  });
  page.on('pageerror', (e) => {
    if (isReal(String(e))) errors.push('pageerror: ' + String(e));
  });
  page.on('response', (r) => {
    if (r.url().includes('$metadata')) metaStatus = r.status();
  });

  await page.goto('/index.html?sap-ui-xx-viewCache=false', { waitUntil: 'load' });
  await page.waitForTimeout(5000); // UI5 açılışı + ilk görünüm + $metadata

  expect(metaStatus, `$metadata status=${metaStatus} (200 beklenir; 401 = kimlik kopuk, -1 = istek hiç gitmedi)`).toBe(200);

  const bodyText = await page.locator('body').innerText().catch(() => '');
  expect(bodyText.trim().length, 'sayfa boş — render çökmüş olabilir').toBeGreaterThan(0);

  if (errors.length) {
    console.log('\nGERÇEK CONSOLE HATALARI:\n' + errors.map((e) => '  x ' + e).join('\n') + '\n');
  }
  expect(errors, 'gerçek console error (agregasyon/routing/undefined) bulundu').toEqual([]);
});
