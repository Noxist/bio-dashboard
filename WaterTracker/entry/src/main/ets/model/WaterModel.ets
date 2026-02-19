/**
 * Data model for water intake tracking.
 */

export interface WaterEntry {
  id: string;
  amount: number;       // millilitres
  timestamp: number;    // Unix epoch in milliseconds
  synced: boolean;
}

export interface DayLog {
  date: string;          // YYYY-MM-DD
  entries: WaterEntry[];
  totalIntake: number;   // sum of all entry amounts (ml)
}

export class WaterModel {
  /**
   * Returns today's date as YYYY-MM-DD.
   */
  public static getTodayDateString(): string {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  /**
   * Generates a short unique ID for a water entry.
   */
  public static generateId(): string {
    return Date.now().toString(36) + Math.random().toString(36).substring(2, 7);
  }

  /**
   * Creates a new WaterEntry with the given amount (ml).
   */
  public static createEntry(amount: number): WaterEntry {
    return {
      id: WaterModel.generateId(),
      amount: amount,
      timestamp: Date.now(),
      synced: false
    };
  }

  /**
   * Sums the amounts of all entries.
   */
  public static calculateTotal(entries: WaterEntry[]): number {
    return entries.reduce((sum: number, e: WaterEntry) => sum + e.amount, 0);
  }

  /**
   * Returns an empty DayLog for the given date string.
   */
  public static emptyLog(dateStr: string): DayLog {
    return { date: dateStr, entries: [], totalIntake: 0 };
  }
}

/**
 * Flat response from the remote health monitoring server.
 * Returned by GET /api/water/instruction.
 */
export interface ServerResponse {
  message: string;
  recommended_amount: number;
  priority: string;
  deadline_minutes: number;
  daily_target_override: number;
  timestamp: string;
  hydration_curve: HydrationCurveData | null;
}

/**
 * Hydration curve data for watch rendering.
 * Describes expected intake over the day + micro-targets.
 */
export interface HydrationCurveData {
  current_ml: number;
  goal_ml: number;
  current_hour: number;
  current_expected_ml: number;
  wake_hour: number;
  sleep_hour: number;
  targets: CurveTarget[];
  expected_curve: CurvePoint[];
}

/**
 * A forward-looking micro-goal (15/30/45/60 min).
 */
export interface CurveTarget {
  minutes: number;
  target_ml: number;
  delta_ml: number;
  label: string;
}

/**
 * A single point on the expected intake curve.
 */
export interface CurvePoint {
  hour: number;
  ml: number;
}
