/**
 * Local persistence service using @ohos.data.preferences.
 * Stores daily water logs and settings as key-value pairs.
 */
import dataPreferences from '@ohos.data.preferences';
import { Constants } from '../common/Constants';
import { WaterEntry, DayLog, WaterModel } from '../model/WaterModel';
import common from '@ohos.app.ability.common';
import hilog from '@ohos.hilog';

const TAG: string = 'StorageService';

export class StorageService {
  private static preferences: dataPreferences.Preferences | null = null;

  /**
   * Must be called once from EntryAbility.onCreate() before any other method.
   */
  public static async init(context: common.UIAbilityContext): Promise<void> {
    try {
      StorageService.preferences = await dataPreferences.getPreferences(context, Constants.PREF_STORE_NAME);
      hilog.info(0x0000, TAG, 'Preferences initialised');
    } catch (err) {
      hilog.error(0x0000, TAG, 'Failed to init preferences: %{public}s', JSON.stringify(err));
    }
  }

  // ---------- Settings ----------

  public static async getDailyGoal(): Promise<number> {
    if (!StorageService.preferences) return Constants.DEFAULT_DAILY_GOAL;
    const val = await StorageService.preferences.get(Constants.KEY_DAILY_GOAL, Constants.DEFAULT_DAILY_GOAL);
    return val as number;
  }

  public static async setDailyGoal(goal: number): Promise<void> {
    if (!StorageService.preferences) return;
    await StorageService.preferences.put(Constants.KEY_DAILY_GOAL, goal);
    await StorageService.preferences.flush();
  }

  public static async getHAUrl(): Promise<string> {
    if (!StorageService.preferences) return Constants.DEFAULT_HA_URL;
    const val = await StorageService.preferences.get(Constants.KEY_HA_URL, Constants.DEFAULT_HA_URL);
    return val as string;
  }

  public static async setHAUrl(url: string): Promise<void> {
    if (!StorageService.preferences) return;
    await StorageService.preferences.put(Constants.KEY_HA_URL, url);
    await StorageService.preferences.flush();
  }

  public static async getHAToken(): Promise<string> {
    if (!StorageService.preferences) return Constants.DEFAULT_HA_TOKEN;
    const val = await StorageService.preferences.get(Constants.KEY_HA_TOKEN, Constants.DEFAULT_HA_TOKEN);
    return val as string;
  }

  public static async setHAToken(token: string): Promise<void> {
    if (!StorageService.preferences) return;
    await StorageService.preferences.put(Constants.KEY_HA_TOKEN, token);
    await StorageService.preferences.flush();
  }

  public static async isHASyncEnabled(): Promise<boolean> {
    if (!StorageService.preferences) return true;
    const val = await StorageService.preferences.get(Constants.KEY_HA_SYNC_ENABLED, true);
    return val as boolean;
  }

  public static async setHASyncEnabled(enabled: boolean): Promise<void> {
    if (!StorageService.preferences) return;
    await StorageService.preferences.put(Constants.KEY_HA_SYNC_ENABLED, enabled);
    await StorageService.preferences.flush();
  }

  // ---------- Water log ----------

  /**
   * Returns the DayLog for the given YYYY-MM-DD date.
   */
  public static async getDayLog(dateStr: string): Promise<DayLog> {
    if (!StorageService.preferences) {
      return WaterModel.emptyLog(dateStr);
    }
    const key = `${Constants.KEY_WATER_LOG}_${dateStr}`;
    const raw = await StorageService.preferences.get(key, '');
    if (!raw || raw === '') {
      return WaterModel.emptyLog(dateStr);
    }
    try {
      return JSON.parse(raw as string) as DayLog;
    } catch (e) {
      hilog.warn(0x0000, TAG, 'Corrupt log for %{public}s, resetting', dateStr);
      return WaterModel.emptyLog(dateStr);
    }
  }

  /**
   * Returns today's DayLog.
   */
  public static async getTodayLog(): Promise<DayLog> {
    return StorageService.getDayLog(WaterModel.getTodayDateString());
  }

  /**
   * Persists the given DayLog.
   */
  public static async saveDayLog(log: DayLog): Promise<void> {
    if (!StorageService.preferences) return;
    const key = `${Constants.KEY_WATER_LOG}_${log.date}`;
    await StorageService.preferences.put(key, JSON.stringify(log));
    await StorageService.preferences.flush();
  }

  /**
   * Adds a new water entry for today and returns the updated DayLog.
   */
  public static async addWaterEntry(amount: number): Promise<DayLog> {
    const log = await StorageService.getTodayLog();
    const entry: WaterEntry = WaterModel.createEntry(amount);
    log.entries.push(entry);
    log.totalIntake = WaterModel.calculateTotal(log.entries);
    await StorageService.saveDayLog(log);
    hilog.info(0x0000, TAG, 'Added %{public}d ml, total now %{public}d ml', amount, log.totalIntake);
    return log;
  }

  /**
   * Removes the most recent entry for today.
   */
  public static async undoLastEntry(): Promise<DayLog> {
    const log = await StorageService.getTodayLog();
    if (log.entries.length > 0) {
      const removed = log.entries.pop();
      log.totalIntake = WaterModel.calculateTotal(log.entries);
      await StorageService.saveDayLog(log);
      hilog.info(0x0000, TAG, 'Undid entry of %{public}d ml', removed?.amount);
    }
    return log;
  }

  /**
   * Returns the last 7 days of water logs (oldest first).
   */
  public static async getWeekHistory(): Promise<DayLog[]> {
    const history: DayLog[] = [];
    const now = new Date();
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now.getTime());
      d.setDate(d.getDate() - i);
      const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      const log = await StorageService.getDayLog(dateStr);
      history.push(log);
    }
    return history;
  }

  // ---------- Drink sizes ----------

  public static async getDrinkSizes(): Promise<number[]> {
    if (!StorageService.preferences) {
      return [Constants.DEFAULT_DRINK_SIZE_1, Constants.DEFAULT_DRINK_SIZE_2, Constants.DEFAULT_DRINK_SIZE_3];
    }
    const s1 = await StorageService.preferences.get(Constants.KEY_DRINK_SIZE_1, Constants.DEFAULT_DRINK_SIZE_1) as number;
    const s2 = await StorageService.preferences.get(Constants.KEY_DRINK_SIZE_2, Constants.DEFAULT_DRINK_SIZE_2) as number;
    const s3 = await StorageService.preferences.get(Constants.KEY_DRINK_SIZE_3, Constants.DEFAULT_DRINK_SIZE_3) as number;
    return [s1, s2, s3];
  }

  public static async setDrinkSize(index: number, value: number): Promise<void> {
    if (!StorageService.preferences) return;
    const keys: string[] = [Constants.KEY_DRINK_SIZE_1, Constants.KEY_DRINK_SIZE_2, Constants.KEY_DRINK_SIZE_3];
    if (index >= 0 && index < keys.length) {
      await StorageService.preferences.put(keys[index], value);
      await StorageService.preferences.flush();
    }
  }

  // ---------- Reminders ----------

  public static async isReminderEnabled(): Promise<boolean> {
    if (!StorageService.preferences) return false;
    const val = await StorageService.preferences.get(Constants.KEY_REMINDER_ENABLED, false);
    return val as boolean;
  }

  public static async setReminderEnabled(enabled: boolean): Promise<void> {
    if (!StorageService.preferences) return;
    await StorageService.preferences.put(Constants.KEY_REMINDER_ENABLED, enabled);
    await StorageService.preferences.flush();
  }

  public static async getReminderInterval(): Promise<number> {
    if (!StorageService.preferences) return Constants.DEFAULT_REMINDER_INTERVAL;
    const val = await StorageService.preferences.get(Constants.KEY_REMINDER_INTERVAL, Constants.DEFAULT_REMINDER_INTERVAL);
    return val as number;
  }

  public static async setReminderInterval(minutes: number): Promise<void> {
    if (!StorageService.preferences) return;
    await StorageService.preferences.put(Constants.KEY_REMINDER_INTERVAL, minutes);
    await StorageService.preferences.flush();
  }

  // ---------- Health server ----------

  public static async getServerUrl(): Promise<string> {
    if (!StorageService.preferences) return Constants.DEFAULT_SERVER_URL;
    const val = await StorageService.preferences.get(Constants.KEY_SERVER_URL, Constants.DEFAULT_SERVER_URL);
    return val as string;
  }

  public static async setServerUrl(url: string): Promise<void> {
    if (!StorageService.preferences) return;
    await StorageService.preferences.put(Constants.KEY_SERVER_URL, url);
    await StorageService.preferences.flush();
  }

  public static async getServerToken(): Promise<string> {
    if (!StorageService.preferences) return Constants.DEFAULT_SERVER_TOKEN;
    const val = await StorageService.preferences.get(Constants.KEY_SERVER_TOKEN, Constants.DEFAULT_SERVER_TOKEN);
    return val as string;
  }

  public static async setServerToken(token: string): Promise<void> {
    if (!StorageService.preferences) return;
    await StorageService.preferences.put(Constants.KEY_SERVER_TOKEN, token);
    await StorageService.preferences.flush();
  }

  public static async isServerEnabled(): Promise<boolean> {
    if (!StorageService.preferences) return false;
    const val = await StorageService.preferences.get(Constants.KEY_SERVER_ENABLED, false);
    return val as boolean;
  }

  public static async setServerEnabled(enabled: boolean): Promise<void> {
    if (!StorageService.preferences) return;
    await StorageService.preferences.put(Constants.KEY_SERVER_ENABLED, enabled);
    await StorageService.preferences.flush();
  }

  // ---------- Entry management ----------

  /**
   * Deletes a specific entry by ID from today's log.
   */
  public static async deleteEntry(entryId: string): Promise<DayLog> {
    const log = await StorageService.getTodayLog();
    log.entries = log.entries.filter((e: WaterEntry) => e.id !== entryId);
    log.totalIntake = WaterModel.calculateTotal(log.entries);
    await StorageService.saveDayLog(log);
    hilog.info(0x0000, TAG, 'Deleted entry %{public}s, total now %{public}d ml', entryId, log.totalIntake);
    return log;
  }
}
