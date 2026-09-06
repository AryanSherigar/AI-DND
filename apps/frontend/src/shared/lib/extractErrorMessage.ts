interface FastApiValidationError {
  loc?: (string | number)[];
  msg?: string;
}

interface AxiosLikeError extends Error {
  response?: { data?: { detail?: unknown } };
}

const isAxiosLikeError = (err: unknown): err is AxiosLikeError =>
  err instanceof Error;

const isValidationErrorList = (
  detail: unknown,
): detail is FastApiValidationError[] =>
  Array.isArray(detail) &&
  detail.every((item) => typeof item === "object" && item !== null);

const formatValidationErrors = (detail: FastApiValidationError[]): string =>
  detail
    .map((item) => {
      const field = item.loc?.[item.loc.length - 1];
      return field && item.msg ? `${field}: ${item.msg}` : item.msg;
    })
    .filter((msg): msg is string => Boolean(msg))
    .join("; ");

export const extractErrorMessage = (err: unknown, fallback: string): string => {
  if (!isAxiosLikeError(err)) return fallback;

  const detail = err.response?.data?.detail;
  if (isValidationErrorList(detail)) {
    return formatValidationErrors(detail) || err.message || fallback;
  }
  if (typeof detail === "string" && detail) return detail;
  return err.message || fallback;
};
