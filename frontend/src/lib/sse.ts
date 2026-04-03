import type { ChatRequest, SSEEvent } from "../types";

export interface SSEHandlers {
  onToolStatus: (tool: string, status: "running" | "done") => void;
  onToken: (content: string) => void;
  onDone: () => void;
  onError: (message: string, code: string) => void;
}

/**
 * POST to /api/v1/chat and parse the SSE stream.
 * Returns an AbortController so the caller can cancel on unmount.
 */
export function streamChat(
  request: ChatRequest,
  handlers: SSEHandlers,
): AbortController {
  const controller = new AbortController();

  (async () => {
    let response: Response;

    try {
      response = await fetch("/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: controller.signal,
      });
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      handlers.onError("Could not connect to backend", "NETWORK_ERROR");
      return;
    }

    if (!response.ok) {
      handlers.onError(`Server error: ${response.status}`, "HTTP_ERROR");
      return;
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE uses \n\n as event separator — process complete lines
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;

        const jsonStr = trimmed.slice(5).trim();
        if (!jsonStr) continue;

        let event: SSEEvent;
        try {
          event = JSON.parse(jsonStr);
        } catch {
          continue; // Malformed line — skip, don't break the stream
        }

        switch (event.type) {
          case "tool_status":
            handlers.onToolStatus(event.tool, event.status);
            break;
          case "token":
            handlers.onToken(event.content);
            break;
          case "done":
            handlers.onDone();
            return;
          case "error":
            handlers.onError(event.message, event.code);
            return;
        }
      }
    }
  })();

  return controller;
}
