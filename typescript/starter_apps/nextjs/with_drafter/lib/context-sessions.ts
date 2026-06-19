const sessionState = new Map<string, string>();

export function loadSessionState(sessionId: string): string | null {
  return sessionState.get(sessionId) ?? null;
}

export function saveSessionState(sessionId: string, exportedState: string): void {
  sessionState.set(sessionId, exportedState);
}
