const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;

if (!backendUrl) {
  throw new Error("Missing NEXT_PUBLIC_BACKEND_URL environment variable");
}

export const BACKEND_URL = backendUrl.replace(/\/$/, "");
