interface AxiosLikeError extends Error {
  response?: { data?: { detail?: string } };
}

const isAxiosLikeError = (err: unknown): err is AxiosLikeError =>
  err instanceof Error;

export const extractErrorMessage = (
  err: unknown,
  fallback: string,
): string => {
  if (isAxiosLikeError(err)) {
    return err.response?.data?.detail || err.message || fallback;
  }
  return fallback;
};
