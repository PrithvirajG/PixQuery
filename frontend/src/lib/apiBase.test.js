import { API_BASE } from './apiBase';

describe('API_BASE', () => {
  test('points at port 8000 on whatever host served the page', () => {
    // jsdom serves from localhost, so that's what the module resolves to. The
    // point of the module is that this tracks window.location rather than being
    // hardcoded — so the same build works over localhost and over a LAN IP.
    expect(API_BASE).toBe(`http://${window.location.hostname}:8000`);
    expect(API_BASE).toBe('http://localhost:8000');
  });
});
