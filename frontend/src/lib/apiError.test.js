import { errorMessage, errorCode } from './apiError';

describe('errorMessage', () => {
  test('returns the backend message field when present', () => {
    const err = { response: { data: { message: 'Invalid credentials', code: 'unauthorized' } } };
    expect(errorMessage(err)).toBe('Invalid credentials');
  });

  test('falls back to the legacy detail field when message is absent', () => {
    const err = { response: { data: { detail: 'Not found' } } };
    expect(errorMessage(err)).toBe('Not found');
  });

  test('falls back to the axios error message when there is no response data', () => {
    const err = { message: 'Network Error' };
    expect(errorMessage(err)).toBe('Network Error');
  });

  test('falls back to the caller-supplied default when nothing else is available', () => {
    const err = {};
    expect(errorMessage(err, 'custom fallback')).toBe('custom fallback');
  });

  test('uses the built-in default fallback when none is supplied', () => {
    expect(errorMessage({})).toBe('Something went wrong. Please try again.');
  });

  test('handles a completely undefined error gracefully', () => {
    expect(errorMessage(undefined, 'fallback')).toBe('fallback');
  });

  test('prefers message over detail when both are present', () => {
    const err = { response: { data: { message: 'from message', detail: 'from detail' } } };
    expect(errorMessage(err)).toBe('from message');
  });
});

describe('errorCode', () => {
  test('returns the machine-readable code from a standard error envelope', () => {
    const err = { response: { data: { code: 'unauthorized' } } };
    expect(errorCode(err)).toBe('unauthorized');
  });

  test('returns undefined when there is no response data', () => {
    expect(errorCode({})).toBeUndefined();
  });

  test('returns undefined for a completely undefined error', () => {
    expect(errorCode(undefined)).toBeUndefined();
  });
});
