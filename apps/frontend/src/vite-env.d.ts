/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CORE_API_URL: string;
  readonly VITE_TRS_URL: string;
  readonly VITE_FIREBASE_API_KEY: string;
  readonly VITE_FIREBASE_AUTH_DOMAIN: string;
  readonly VITE_FIREBASE_PROJECT_ID: string;
  readonly VITE_FIREBASE_STORAGE_BUCKET: string;
  readonly VITE_FIREBASE_MESSAGING_SENDER_ID: string;
  readonly VITE_FIREBASE_APP_ID: string;
  readonly VITE_MEASUREMENT_ID: string;
  readonly VITE_DEV_USER_ID?: string;
  readonly VITE_JUDGE_EMAIL?: string;
  readonly VITE_JUDGE_PASSWORD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
