/**
 * Application-wide constants for the Water Tracker watch app.
 *
 * Spacing values follow the HarmonyOS Wearable Design Spacing Parameters
 * for round watches (466 × 466 px = 233 × 233 vp).
 *
 * @see https://developer.huawei.com/consumer/en/doc/design-guides/spacing-parameters-0000002202912577
 */
export class Constants {
  // ── Defaults ──
  public static readonly DEFAULT_DAILY_GOAL: number = 2500;
  public static readonly QUICK_ADD_AMOUNTS: number[] = [100, 250, 500];
  public static readonly CROWN_STEP: number = 50;

  // ── Round watch layout (vp) ──
  public static readonly MARGIN_LEFT: number = 26;
  public static readonly MARGIN_RIGHT: number = 26;
  public static readonly PADDING_TOP: number = 20;
  public static readonly PADDING_CONTENT_TOP: number = 40;
  public static readonly PADDING_CONTENT_BOTTOM: number = 36;
  public static readonly SCREEN_SIZE_VP: number = 233;

  // ── Preference keys ──
  public static readonly PREF_STORE_NAME: string = 'water_tracker_prefs';
  public static readonly KEY_DAILY_GOAL: string = 'daily_goal';
  public static readonly KEY_HA_URL: string = 'ha_url';
  public static readonly KEY_HA_TOKEN: string = 'ha_token';
  public static readonly KEY_WATER_LOG: string = 'water_log';
  public static readonly KEY_HA_SYNC_ENABLED: string = 'ha_sync_enabled';

  // ── Theme colours (dark AMOLED-optimised) ──
  public static readonly COLOR_PRIMARY: string = '#4FC3F7';
  public static readonly COLOR_BACKGROUND: string = '#000000';
  public static readonly COLOR_SURFACE: string = '#1C1C1E';
  public static readonly COLOR_ACCENT: string = '#00E5FF';
  public static readonly COLOR_TEXT_PRIMARY: string = '#FFFFFF';
  public static readonly COLOR_TEXT_SECONDARY: string = '#8E8E93';
  public static readonly COLOR_PROGRESS_BG: string = '#2C2C2E';
  public static readonly COLOR_SUCCESS: string = '#34C759';
  public static readonly COLOR_WARNING: string = '#FF9F0A';

  // ── Configurable drink sizes ──
  public static readonly DEFAULT_DRINK_SIZE_1: number = 100;
  public static readonly DEFAULT_DRINK_SIZE_2: number = 250;
  public static readonly DEFAULT_DRINK_SIZE_3: number = 500;
  public static readonly DRINK_SIZE_STEP: number = 25;
  public static readonly DRINK_SIZE_MIN: number = 25;
  public static readonly DRINK_SIZE_MAX: number = 1000;

  // ── Reminder settings ──
  public static readonly DEFAULT_REMINDER_INTERVAL: number = 60;
  public static readonly REMINDER_CHECK_MS: number = 60000;

  // ── Health monitoring server ──
  public static readonly DEFAULT_SERVER_URL: string = '';
  public static readonly DEFAULT_SERVER_TOKEN: string = '';
  public static readonly SERVER_POLL_MS: number = 900000;

  // ── Additional preference keys ──
  public static readonly KEY_DRINK_SIZE_1: string = 'drink_size_1';
  public static readonly KEY_DRINK_SIZE_2: string = 'drink_size_2';
  public static readonly KEY_DRINK_SIZE_3: string = 'drink_size_3';
  public static readonly KEY_REMINDER_ENABLED: string = 'reminder_enabled';
  public static readonly KEY_REMINDER_INTERVAL: string = 'reminder_interval';
  public static readonly KEY_SERVER_URL: string = 'server_url';
  public static readonly KEY_SERVER_TOKEN: string = 'server_token';
  public static readonly KEY_SERVER_ENABLED: string = 'server_enabled';

  // ── Home Assistant (hardcoded) ──
  public static readonly DEFAULT_HA_URL: string =
    'https://irsmznxjuulyw58u7n2fy9bu6f8qqv4w.ui.nabu.casa';
  public static readonly DEFAULT_HA_TOKEN: string =
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI5YzMxZjRkMTcwOTg0Y2YwODZlZWY3YWYwNDY0ODIwZCIsImlhdCI6MTc3MTQxMzI4MiwiZXhwIjoyMDg2NzczMjgyfQ.K1ZD5RadxsojTSXSNxmJoh5_n8YZCbNDVrLoJ8QdGZ4';
  public static readonly HA_ENTITY_ID: string = 'sensor.water_tracker_daily';
}
