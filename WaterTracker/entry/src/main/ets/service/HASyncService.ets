/**
 * Home Assistant sync service.
 * Pushes the current daily water intake to a Home Assistant sensor entity
 * via the REST API (works over Nabu Casa or any exposed HA instance).
 */
import http from '@ohos.net.http';
import { StorageService } from './StorageService';
import { DayLog } from '../model/WaterModel';
import { Constants } from '../common/Constants';
import hilog from '@ohos.hilog';

const TAG: string = 'HASyncService';

// Typed interfaces for ArkTS strict mode
class HAStateAttributes {
  public unit_of_measurement: string = '';
  public friendly_name: string = '';
  public icon: string = '';
  public device_class: string = '';
  public state_class: string = '';
  public date: string = '';
  public entry_count: number = 0;
  public last_entry_amount: number = 0;
  public last_entry_time: string = '';
  public daily_goal: number = 0;
  public goal_reached: boolean = false;
}

class HAStatePayload {
  public state: string = '';
  public attributes: HAStateAttributes = new HAStateAttributes();
}

class TestConnectionResult {
  public success: boolean = false;
  public message: string = '';
}

function buildAuthHeader(token: string): object {
  return JSON.parse(`{"Authorization":"Bearer ${token}","Content-Type":"application/json"}`);
}

export class HASyncService {

  /**
   * Pushes the full DayLog state to HA as sensor.water_tracker_daily.
   * Returns true on success.
   */
  public static async syncToHA(dayLog: DayLog): Promise<boolean> {
    const syncEnabled = await StorageService.isHASyncEnabled();
    if (!syncEnabled) {
      return false;
    }

    const url = await StorageService.getHAUrl();
    const token = await StorageService.getHAToken();
    if (!url || !token) {
      hilog.warn(0x0000, TAG, 'HA URL or token not configured');
      return false;
    }

    const endpoint = `${url}/api/states/${Constants.HA_ENTITY_ID}`;
    const dailyGoal = await StorageService.getDailyGoal();

    const lastEntry = dayLog.entries.length > 0
      ? dayLog.entries[dayLog.entries.length - 1]
      : null;

    const attrs = new HAStateAttributes();
    attrs.unit_of_measurement = 'ml';
    attrs.friendly_name = 'Water Intake Today';
    attrs.icon = 'mdi:cup-water';
    attrs.device_class = 'water';
    attrs.state_class = 'total_increasing';
    attrs.date = dayLog.date;
    attrs.entry_count = dayLog.entries.length;
    attrs.last_entry_amount = lastEntry ? lastEntry.amount : 0;
    attrs.last_entry_time = lastEntry ? new Date(lastEntry.timestamp).toISOString() : '';
    attrs.daily_goal = dailyGoal;
    attrs.goal_reached = dayLog.totalIntake >= dailyGoal;

    const statePayload = new HAStatePayload();
    statePayload.state = String(dayLog.totalIntake);
    statePayload.attributes = attrs;

    const payload: string = JSON.stringify(statePayload);

    const httpRequest = http.createHttp();
    try {
      const response = await httpRequest.request(endpoint, {
        method: http.RequestMethod.POST,
        header: buildAuthHeader(token),
        extraData: payload,
        connectTimeout: 10000,
        readTimeout: 10000
      } as http.HttpRequestOptions);

      const code = response.responseCode;
      if (code >= 200 && code < 300) {
        hilog.info(0x0000, TAG, 'Synced %{public}d ml to HA', dayLog.totalIntake);
        return true;
      } else {
        hilog.error(0x0000, TAG, 'HA returned HTTP %{public}d', code);
        return false;
      }
    } catch (err) {
      hilog.error(0x0000, TAG, 'Sync error: %{public}s', JSON.stringify(err));
      return false;
    } finally {
      httpRequest.destroy();
    }
  }

  /**
   * Quick connectivity check -- GETs /api/ which returns {"message":"API running."}
   */
  public static async testConnection(): Promise<TestConnectionResult> {
    const url = await StorageService.getHAUrl();
    const token = await StorageService.getHAToken();
    const result = new TestConnectionResult();
    if (!url || !token) {
      result.success = false;
      result.message = 'URL or token missing';
      return result;
    }

    const httpRequest = http.createHttp();
    try {
      const response = await httpRequest.request(`${url}/api/`, {
        method: http.RequestMethod.GET,
        header: buildAuthHeader(token),
        connectTimeout: 10000,
        readTimeout: 10000
      } as http.HttpRequestOptions);

      if (response.responseCode === 200) {
        result.success = true;
        result.message = 'Connected';
      } else if (response.responseCode === 401) {
        result.success = false;
        result.message = 'Invalid token (401)';
      } else {
        result.success = false;
        result.message = `HTTP ${response.responseCode}`;
      }
      return result;
    } catch (err) {
      result.success = false;
      result.message = String((err as Error).message || 'Connection failed');
      return result;
    } finally {
      httpRequest.destroy();
    }
  }
}
