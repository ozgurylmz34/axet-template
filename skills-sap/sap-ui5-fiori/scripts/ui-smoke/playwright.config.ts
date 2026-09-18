import { defineConfig } from '@playwright/test';

// Lokal UI5 render smoke — run_ui_smoke.py çağırır.
// SAP kimliği: lokal fiori-tools-proxy gelen Basic auth'u backend'e iletir → httpCredentials ile $metadata açılır.
// Kimlik env'den gelir (run_ui_smoke.py FIORI_TOOLS_USER/PASSWORD → SAP_USER/SAP_PASS); config'e YAZILMAZ.

const BASE_URL = process.env.SMOKE_BASE_URL || 'http://localhost:8080';
const SAP_USER = process.env.SAP_USER || '';
const SAP_PASS = process.env.SAP_PASS || '';

// Varsayılan koşum YALNIZ jenerik smoke: klasöre eklenen uygulamaya özel spec başka bir uygulamanın
// portunda koşarsa yanlış blok üretir. Uygulamaya özel spec --spec ile AÇIKÇA seçilir.
const DEFAULT_SPEC = 'ui.smoke.spec.ts';

export default defineConfig({
  testDir: '.',
  testMatch: process.env.SMOKE_SPEC ? [process.env.SMOKE_SPEC] : [DEFAULT_SPEC],
  timeout: 60_000,
  retries: 0, // hesap kilidi önlemi: yanlış kimlikte tekrar deneme YOK
  reporter: [['list']],
  use: {
    baseURL: BASE_URL,
    headless: true,
    ignoreHTTPSErrors: true,
    httpCredentials: SAP_USER ? { username: SAP_USER, password: SAP_PASS } : undefined,
  },
});
