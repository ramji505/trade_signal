/**
 * Dynamic API Base URL resolution:
 * Automatically uses the host's IP/domain on port 8000 so that both local
 * and remote (e.g. AWS EC2) browser requests hit the correct backend.
 */
export const getApiBaseUrl = (): string => {
  if (process.env.NEXT_PUBLIC_API_URL && !process.env.NEXT_PUBLIC_API_URL.includes("localhost")) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
};
