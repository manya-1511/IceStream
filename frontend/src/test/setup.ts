import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement ResizeObserver, which Recharts' ResponsiveContainer
// and React Flow's viewport both rely on to measure their container.
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// @ts-expect-error -- test-only global polyfill
global.ResizeObserver = ResizeObserverMock;

// jsdom doesn't implement WebSocket either. The smoke test only needs the
// app to mount without throwing, not a real live connection.
class WebSocketMock {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  onopen: (() => void) | null = null;
  onmessage: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close() {}
}
// @ts-expect-error -- test-only global polyfill
global.WebSocket = WebSocketMock;
