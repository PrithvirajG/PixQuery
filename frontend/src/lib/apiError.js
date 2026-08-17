// Reads the user-facing message out of a failed API response.
//
// The backend returns a standard error envelope:
//   { error: true, code, message, status }
// `message` is always the text meant for the user. We fall back to the legacy
// `detail` shape and the axios error message so nothing breaks mid-transition,
// and finally to a caller-supplied default.
export function errorMessage(err, fallback = 'Something went wrong. Please try again.') {
  const data = err?.response?.data;
  return data?.message ?? data?.detail ?? err?.message ?? fallback;
}

// Machine-readable code for branching on specific errors (e.g. show a login
// modal on `unauthorized`). Returns undefined for non-standard responses.
export function errorCode(err) {
  return err?.response?.data?.code;
}
