const sessionState = new Map<string, string>();

export function loadSessionState(sessionId: string): string | null {
  return sessionState.get(sessionId) ?? null;
}

export function saveSessionState(sessionId: string, checkpoint: string): void {
  sessionState.set(sessionId, checkpoint);
}
