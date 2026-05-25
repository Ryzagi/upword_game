import { create } from "zustand";

import type { WsStatus } from "../ws/client";

interface ConnectionState {
  status: WsStatus;
  closeCode: number | null;
  setStatus: (status: WsStatus, closeCode?: number) => void;
  reset: () => void;
}

export const useConnectionStore = create<ConnectionState>((set) => ({
  status: "idle",
  closeCode: null,
  setStatus: (status, closeCode) =>
    set({ status, closeCode: closeCode ?? null }),
  reset: () => set({ status: "idle", closeCode: null }),
}));
