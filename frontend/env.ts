const backendUrl = process.env.NEXT_BACKEND_URL;

if (!backendUrl) {
  throw new Error("Missing NEXT_BACKEND_URL environment variable");
}

export const BACKEND_URL = backendUrl.replace(/\/$/, "");
