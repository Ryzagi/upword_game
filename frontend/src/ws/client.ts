import type { ClientEvent, ServerEvent } from "./events";
import { wsUrl } from "./events";

export type WsStatus = "idle" | "connecting" | "open" | "closed";

interface WsClientOpts {
  code: string;
  token: string;
  onEvent: (event: ServerEvent) => void;
  onStatusChange: (status: WsStatus, closeCode?: number) => void;
  /** Initial reconnect delay in ms. Doubles up to a cap. */
  reconnectInitialMs?: number;
  reconnectMaxMs?: number;
  /** Close codes for which we should NOT auto-reconnect. */
  fatalCloseCodes?: ReadonlySet<number>;
}

const DEFAULT_INITIAL_DELAY = 500;
const DEFAULT_MAX_DELAY = 10_000;
const DEFAULT_FATAL_CODES: ReadonlySet<number> = new Set([4401, 4404]);

/**
 * Thin WebSocket wrapper with auto-reconnect on transient drops.
 * Replies to server pings transparently. Routes events to the consumer.
 */
export class WsClient {
  private ws: WebSocket | null = null;
  private status: WsStatus = "idle";
  private reconnectDelay: number;
  private readonly initialDelay: number;
  private readonly maxDelay: number;
  private readonly fatalCodes: ReadonlySet<number>;
  private closed = false;
  private reconnectTimer: number | null = null;

  constructor(private readonly opts: WsClientOpts) {
    this.initialDelay = opts.reconnectInitialMs ?? DEFAULT_INITIAL_DELAY;
    this.maxDelay = opts.reconnectMaxMs ?? DEFAULT_MAX_DELAY;
    this.reconnectDelay = this.initialDelay;
    this.fatalCodes = opts.fatalCloseCodes ?? DEFAULT_FATAL_CODES;
  }

  connect(): void {
    if (this.closed) return;
    this.setStatus("connecting");
    const ws = new WebSocket(wsUrl(this.opts.code, this.opts.token));
    this.ws = ws;
    ws.addEventListener("open", () => {
      this.reconnectDelay = this.initialDelay;
      this.setStatus("open");
    });
    ws.addEventListener("message", (e) => {
      let parsed: ServerEvent;
      try {
        parsed = JSON.parse(e.data) as ServerEvent;
      } catch {
        return;
      }
      if (parsed.type === "server/ping") {
        this.send({ type: "client/pong" });
        return;
      }
      this.opts.onEvent(parsed);
    });
    ws.addEventListener("close", (e) => {
      this.ws = null;
      this.setStatus("closed", e.code);
      if (this.closed) return;
      if (this.fatalCodes.has(e.code)) {
        this.closed = true;
        return;
      }
      this.scheduleReconnect();
    });
    ws.addEventListener("error", () => {
      // The close handler will run after error, which is where we recover.
    });
  }

  send(event: ClientEvent): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return false;
    }
    this.ws.send(JSON.stringify(event));
    return true;
  }

  close(): void {
    this.closed = true;
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws !== null) {
      this.ws.close();
      this.ws = null;
    }
  }

  private setStatus(status: WsStatus, code?: number): void {
    if (this.status === status) return;
    this.status = status;
    this.opts.onStatusChange(status, code);
  }

  private scheduleReconnect(): void {
    if (this.closed) return;
    const delay = this.reconnectDelay;
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay);
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }
}
