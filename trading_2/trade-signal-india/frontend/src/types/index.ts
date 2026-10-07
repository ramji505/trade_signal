export interface SystemHealth {
  status: string;
  app: string;
  version: string;
  environment: string;
  mode: string;
  order_execution: boolean;
  disclaimer: string;
}

export interface MarketStatus {
  status: "OPEN" | "CLOSED" | "PRE_OPEN" | "POST_CLOSE";
  data_quality: "HEALTHY" | "STALE" | "DISCONNECTED";
  is_mock: boolean;
  instrument: string;
}

export interface SignalData {
  signal_id: string | null;
  symbol: string;
  timestamp: string;
  direction: "BUY" | "SELL" | "WAIT";
  entry_price: number | null;
  stop_loss: number | null;
  target_1: number | null;
  target_2: number | null;
  score: number;
  quality: "NO_TRADE" | "WEAK" | "MODERATE" | "STRONG" | "VERY_STRONG";
  timeframe: string;
  market_regime: string;
  timeframe_states?: Record<string, string>;
  status: "CREATED" | "ACTIVE" | "TARGET_HIT" | "STOP_HIT" | "TIMEOUT" | "CANCELLED";
  reason: string | null;
}
