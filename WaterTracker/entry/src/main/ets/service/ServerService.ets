/**
 * ServerService — communicates with a remote health monitoring server.
 *
 * The server implements two endpoints:
 *   POST /api/water/report       — receives the watch's current hydration status
 *   GET  /api/water/instruction   — returns a drinking instruction for the watch
 *
 * Authentication is via Bearer token in the Authorization header.
 * Server URL and token are configured in Constants.ets.
 *
 * @see README.md for the full API contract
 */
import http from '@ohos.net.http';
import { StorageService } from './StorageService';
import { DayLog, ServerResponse, HydrationCurveData } from '../model/WaterModel';
import { Constants } from '../common/Constants';
import hilog from '@ohos.hilog';

const TAG: string = 'ServerService';

class WatchStatusReport {
  public device_id: string = 'watch_ultra2';
  public current_intake: number = 0;
  public daily_goal: number = 0;
  public entry_count: number = 0;
  public last_drink_time: string = '';
  public timestamp: string = '';
}

function buildServerHeader(token: string): object {
  if (token.length > 0) {
    return JSON.parse(`{"Authorization":"Bearer ${token}","Content-Type":"application/json"}`);
  }
  return JSON.parse('{"Content-Type":"application/json"}');
}

export class ServerService {

  /**
   * POST current hydration status to the server.
   */
  public static async reportStatus(): Promise<boolean> {
    const url: string = await StorageService.getServerUrl();
    const token: string = await StorageService.getServerToken();
    if (url.length === 0) {
      return false;
    }

    const log: DayLog = await StorageService.getTodayLog();
    const goal: number = await StorageService.getDailyGoal();
    const lastEntry = log.entries.length > 0
      ? log.entries[log.entries.length - 1]
      : null;

    const report: WatchStatusReport = new WatchStatusReport();
    report.device_id = 'watch_ultra2';
    report.current_intake = log.totalIntake;
    report.daily_goal = goal;
    report.entry_count = log.entries.length;
    report.last_drink_time = lastEntry ? new Date(lastEntry.timestamp).toISOString() : '';
    report.timestamp = new Date().toISOString();

    const httpRequest = http.createHttp();
    try {
      const response = await httpRequest.request(`${url}/api/water/report`, {
        method: http.RequestMethod.POST,
        header: buildServerHeader(token),
        extraData: JSON.stringify(report),
        connectTimeout: 15000,
        readTimeout: 15000
      } as http.HttpRequestOptions);

      const ok: boolean = response.responseCode >= 200 && response.responseCode < 300;
      if (ok) {
        hilog.info(0x0000, TAG, 'Status reported: %{public}d ml', log.totalIntake);
      } else {
        hilog.warn(0x0000, TAG, 'Report HTTP %{public}d', response.responseCode);
      }
      return ok;
    } catch (err) {
      hilog.error(0x0000, TAG, 'Report error: %{public}s', String(err));
      return false;
    } finally {
      httpRequest.destroy();
    }
  }

  /**
   * GET the latest drinking instruction from the server.
   * Returns null when no instruction is available or on error.
   */
  public static async fetchInstruction(): Promise<ServerResponse | null> {
    const url: string = await StorageService.getServerUrl();
    const token: string = await StorageService.getServerToken();
    if (url.length === 0) {
      return null;
    }

    const log: DayLog = await StorageService.getTodayLog();
    const goal: number = await StorageService.getDailyGoal();
    const lastEntry = log.entries.length > 0
      ? log.entries[log.entries.length - 1]
      : null;
    const lastTime: string = lastEntry
      ? new Date(lastEntry.timestamp).toISOString()
      : '';

    const query: string =
      `?current_intake=${log.totalIntake}` +
      `&daily_goal=${goal}` +
      `&last_drink_time=${encodeURIComponent(lastTime)}`;

    const httpRequest = http.createHttp();
    try {
      const response = await httpRequest.request(`${url}/api/water/instruction${query}`, {
        method: http.RequestMethod.GET,
        header: buildServerHeader(token),
        connectTimeout: 15000,
        readTimeout: 15000
      } as http.HttpRequestOptions);

      if (response.responseCode === 200 && response.result) {
        const parsed: ServerResponse = JSON.parse(response.result as string) as ServerResponse;
        if (parsed.message && parsed.message.length > 0) {
          hilog.info(0x0000, TAG, 'Instruction: %{public}s', parsed.message);
        }
        return parsed;
      }
      return null;
    } catch (err) {
      hilog.error(0x0000, TAG, 'Fetch error: %{public}s', String(err));
      return null;
    } finally {
      httpRequest.destroy();
    }
  }
}
