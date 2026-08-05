/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Mapbox-token (obligatorisk för kartan) */
  readonly VITE_MAPBOX_TOKEN?: string;
  /** Bas-URL till backend-API:t. Tom sträng = relativa anrop via proxy. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
