
# Copilot Prompt — Option B: HR + Sleep Companion Module

> Paste this entire file as context when working on the WaterTracker HarmonyOS app.
> It adds heart-rate and sleep monitoring to the existing watch app.

---

## 1. Goal

Add **heart-rate (HR)** and **sleep** monitoring to the existing
**WaterTracker** HarmonyOS watch app (Huawei Watch Ultimate 2, HarmonyOS 5).
Both features must:

- Have **individual on/off toggles** in SettingsPage (default: **off**).
- Have a **"Test" button** next to each toggle (sends one sample payload, shows ✓/✗).
- Be **invisible** in the main UI — no extra pages, no complications.
  The only trace is the two toggle+test rows inside
  `SettingsPage.ets` → "Health Monitoring" section.
- Push data to the **bio-dashboard** server via the same auth mechanism
  the water tracker already uses (Bearer token, same base URL).

---

## 2. Existing Codebase Context

### 2.1 File layout you'll touch

```
WaterTracker/entry/src/main/ets/
├── common/Constants.ets          ← add pref keys + defaults
├── model/WaterModel.ets          ← add HR/sleep data interfaces
├── service/
│   ├── StorageService.ets        ← add get/set for HR & sleep prefs
│   ├── ServerService.ets         ← add pushHeartRate() & pushSleep()
│   └── HealthMonitorService.ets  ← NEW — background HR + sleep logic
├── pages/
│   └── SettingsPage.ets          ← add "Health Monitoring" card
└── entryability/EntryAbility.ets ← start/stop HealthMonitorService
```

### 2.2 Auth & networking pattern

`ServerService.ets` already implements:
- `buildServerHeader(token)` → `{ Authorization: "Bearer <token>", Content-Type: "application/json" }`
- Base URL from `StorageService.getServerUrl()` (default: `https://bioapi.thegrandprinterofmemesandunfinitetodosservanttonox.tech`)
- Token from `StorageService.getServerToken()` (default: `bio_leandro_2026_secret`)
- HTTP via `@ohos.net.http`

Follow the same pattern for the new endpoints.

### 2.3 Preference keys pattern

`Constants.ets` has `KEY_*` strings and `StorageService` uses
`@ohos.data.preferences` to persist them.

### 2.4 Server API — existing endpoints the companion should know about

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/water/report` | Report water intake, **now returns instruction inline** (merged response: `{ status, instruction: { message, recommended_amount, priority, deadline_minutes, daily_target_override, velocity_warning, events_today, adaptive_curve, hydration_curve } }`) |
| GET | `/api/water/instruction` | Fetch drinking instruction (same instruction shape as above) |
| DELETE | `/api/water/intake/last` | Undo last water entry |
| POST | `/api/health` | **This is the endpoint for HR + sleep** |
| POST | `/api/weight` | Log weight |
| GET | `/api/status` | Health check (used by `testConnection()`) |

### 2.5 Server API — the `POST /api/health` endpoint (your target)

**Request body** (`HealthSnapshotRequest`):
```json
{
  "heart_rate": 72.0,        // optional — current BPM
  "resting_hr": 58.0,        // optional — resting HR (if available)
  "hrv": 42.0,               // optional — HRV in ms (if available)
  "sleep_duration": 7.5,     // optional — hours slept (float)
  "sleep_confidence": 0.85,  // optional — 0.0–1.0
  "spo2": 97.0,              // optional — SpO2 %
  "respiratory_rate": 16.0,  // optional — breaths/min
  "steps": 4200,             // optional — daily steps (int)
  "calories": 320.0,         // optional — active kcal
  "source": "watch",         // MUST be "watch" when sent from the watch
  "timestamp": "2026-02-20T08:30:00"  // optional (server defaults to now)
}
```

All fields are optional. Send only what you collected.
**Auth**: `x-api-key` header OR `Authorization: Bearer <token>` — the server checks both.
The watch already uses Bearer.

**Response**: `{ "id": <int>, "status": "ok" }`

### 2.6 Adaptive Curve (new since last sync)

The instruction response now includes an `adaptive_curve` field:
```json
{
  "adaptive_curve": {
    "points": [
      { "hour": 7.0, "ideal_ml": 0, "catchup_ml": 0 },
      { "hour": 7.5, "ideal_ml": 160, "catchup_ml": 220 },
      ...
    ],
    "current_hour": 14.25,
    "actual_ml": 1800,
    "goal_ml": 3200,
    "ideal_now_ml": 1900,
    "catchup_now_ml": 2100,
    "status": "behind"
  }
}
```
The watch already renders `hydration_curve` — the new `adaptive_curve` is
available but rendering it is **out of scope** for this task. Just make sure
the `ServerResponse` interface accepts it (add `adaptive_curve: object | null`).

### 2.7 Database schema (server-side, read-only context)

The `health_snapshots` table stores:
```
id, timestamp, heart_rate, resting_hr, hrv, sleep_duration,
sleep_confidence, spo2, respiratory_rate, steps, calories, source
```
Source values: `'ha'`, `'manual'`, `'watch'`.
These feed into `compute_bio_score()` on the server.

---

## 3. Implementation Spec

### 3.1 Constants.ets additions

```typescript
// ── Health monitoring ──
public static readonly KEY_HR_ENABLED: string = 'hr_monitoring_enabled';
public static readonly KEY_SLEEP_ENABLED: string = 'sleep_monitoring_enabled';
public static readonly HR_SAMPLE_INTERVAL_MS: number = 600000;  // 10 min
public static readonly HR_PUSH_INTERVAL_MS: number = 900000;    // 15 min (match server poll)
public static readonly SLEEP_PUSH_DELAY_MS: number = 300000;    // 5 min after wake
```

### 3.2 WaterModel.ets additions

Add these interfaces:

```typescript
/** Payload sent to POST /api/health from the watch. */
export interface HealthPushPayload {
  heart_rate?: number;
  resting_hr?: number;
  hrv?: number;
  sleep_duration?: number;
  sleep_confidence?: number;
  spo2?: number;
  steps?: number;
  calories?: number;
  source: string;        // always "watch"
  timestamp?: string;
}

/** Also add to ServerResponse: */
// adaptive_curve: object | null;
```

### 3.3 StorageService.ets additions

```typescript
public static async isHREnabled(): Promise<boolean> { ... }
public static async setHREnabled(v: boolean): Promise<void> { ... }
public static async isSleepEnabled(): Promise<boolean> { ... }
public static async setSleepEnabled(v: boolean): Promise<void> { ... }
```

Default both to `false`.

### 3.4 ServerService.ets additions

Add two new public static methods:

```typescript
/**
 * Push a heart-rate snapshot to the server.
 * POST /api/health with source="watch".
 */
public static async pushHeartRate(payload: HealthPushPayload): Promise<boolean> {
  // Same pattern as reportStatus():
  // 1. Get url + token from StorageService
  // 2. POST to `${url}/api/health`
  // 3. Return true on 2xx
  ...
}

/**
 * Push a sleep summary to the server.
 * POST /api/health with source="watch", sleep_duration + sleep_confidence.
 */
public static async pushSleep(payload: HealthPushPayload): Promise<boolean> {
  // Identical HTTP pattern, different fields populated
  ...
}

/**
 * One-shot test push (used by the "Test" buttons in Settings).
 * Sends a dummy snapshot with source="watch" and heart_rate=0.
 * Returns { success, message } like testConnection().
 */
public static async testHealthPush(): Promise<ServerTestResult> {
  // POST /api/health with { source: "watch", heart_rate: 0 }
  // On 200: success=true, message="Health endpoint OK"
  // On 401: success=false, message="Invalid token (401)"
  // On error: success=false, message="Connection failed"
  ...
}
```

### 3.5 HealthMonitorService.ets (NEW file)

```
WaterTracker/entry/src/main/ets/service/HealthMonitorService.ets
```

This is the **background orchestrator**. It does NOT have UI.

```typescript
import sensor from '@ohos.sensor';           // HR sensor access
import { Constants } from '../common/Constants';
import { StorageService } from './StorageService';
import { ServerService } from './ServerService';
import { HealthPushPayload } from '../model/WaterModel';
import hilog from '@ohos.hilog';

const TAG: string = 'HealthMonitorService';

export class HealthMonitorService {
  private static hrIntervalId: number = -1;
  private static hrBuffer: number[] = [];   // rolling BPM samples

  /**
   * Called from EntryAbility.onCreate().
   * Starts HR + sleep monitoring if enabled.
   */
  public static async init(): Promise<void> {
    if (await StorageService.isHREnabled()) {
      HealthMonitorService.startHR();
    }
    if (await StorageService.isSleepEnabled()) {
      HealthMonitorService.startSleep();
    }
  }

  /** Start periodic HR sampling + server push. */
  public static startHR(): void { ... }

  /** Stop HR monitoring. */
  public static stopHR(): void { ... }

  /** Start sleep detection listener. */
  public static startSleep(): void { ... }

  /** Stop sleep monitoring. */
  public static stopSleep(): void { ... }
}
```

#### HR flow:

1. Use `sensor.on(sensor.SensorId.HEART_RATE, callback, { interval: HR_SAMPLE_INTERVAL_MS })`.
2. Each callback: push BPM to `hrBuffer` (keep last 3 samples = 30 min).
3. Every `HR_PUSH_INTERVAL_MS` (15 min), compute:
   - `heart_rate` = latest sample
   - `resting_hr` = min of buffer (approximation)
4. Call `ServerService.pushHeartRate({ heart_rate, resting_hr, source: "watch" })`.
5. Clear buffer after push.

> **Important**: The Huawei Watch Ultimate 2 uses HarmonyOS sensor API:
> ```typescript
> import sensor from '@ohos.sensor';
> sensor.on(sensor.SensorId.HEART_RATE, (data) => {
>   const bpm: number = data.heartRate;
> }, { interval: 600000000 }); // nanoseconds!
> ```
> The interval is in **nanoseconds** for `@ohos.sensor`. Convert ms → ns.

#### Sleep flow:

The Huawei Watch can detect sleep through various approaches. Use the
simplest reliable method:

**Option A** (preferred): Use `@ohos.sensor` sleep detector if available:
```typescript
sensor.on(sensor.SensorId.WEAR_DETECTION, (data) => {
  // data.value: 1 = on wrist, 0 = off wrist
});
```
Combined with the HA `input_boolean.inbed` / `input_boolean.sleepmode`
sensors that the server already polls, the watch can detect sleep start/end.

**Option B** (simpler): Just send HR data and let the server figure out
sleep from the HA sensors it already reads (`sleep_duration` from Google Fit
via HealthSync).

**Recommended**: Go with **Option B** — the server already imports
`sensor.pixel_9_pro_xl_sleep_duration_2` from HA every 15 min. The watch
should NOT try to compute its own sleep duration. If the user enables
sleep monitoring, the watch should:
1. When the user has been still for 30+ min with low HR (< 60 BPM average
   over 3 samples), log it as potential sleep onset.
2. On wrist re-detection or first motion after long still period, compute
   duration and push `{ sleep_duration: <hours>, sleep_confidence: 0.5, source: "watch" }`.
3. The server will reconcile this with Google Fit data if available.

> For MVP: If sleep detection is too complex, just enable the toggle but
> **only push HR data during all hours** (including sleep). The server-side
> bio_engine already uses Google Fit sleep data via HA. Mark this decision
> clearly in code comments.

### 3.6 SettingsPage.ets additions

Add a new **"Health Monitoring"** card section between the existing
"Server Sync" card and the bottom of the settings list. The card should
follow the exact same styling pattern as the existing cards.

```
┌─────────────────────────────────────┐
│ 🫀  Health Monitoring               │
│                                     │
│  Heart Rate    [━━━━○]  [Test]      │
│  Sleep Track   [━━━━○]  [Test]      │
│                                     │
│  (small caption: "Data is sent to   │
│   your health server every 15 min") │
└─────────────────────────────────────┘
```

State variables to add:
```typescript
@State private hrEnabled: boolean = false;
@State private sleepEnabled: boolean = false;
@State private hrTestStatus: string = '';
@State private sleepTestStatus: string = '';
```

**Toggle behavior**:
- On toggle HR → call `StorageService.setHREnabled(value)`,
  then `HealthMonitorService.startHR()` or `.stopHR()`.
- On toggle Sleep → same pattern with sleep methods.
- Test button → call `ServerService.testHealthPush()`,
  show ✓ or ✗ in `hrTestStatus` / `sleepTestStatus` for 3 seconds.

Load initial values in `loadSettings()`.

### 3.7 EntryAbility.ets changes

In `onCreate()`, after existing initialization, add:
```typescript
import { HealthMonitorService } from '../service/HealthMonitorService';
// ...
await HealthMonitorService.init();
```

In `onDestroy()`:
```typescript
HealthMonitorService.stopHR();
HealthMonitorService.stopSleep();
```

### 3.8 ServerResponse interface update

In `WaterModel.ets`, update `ServerResponse`:
```typescript
export interface ServerResponse {
  message: string;
  recommended_amount: number;
  priority: string;
  deadline_minutes: number;
  daily_target_override: number;
  timestamp: string;
  velocity_warning?: string;       // NEW — e.g. "Langsamer trinken"
  events_today?: number;           // NEW — how many drinks today
  hydration_curve: HydrationCurveData | null;
  adaptive_curve: object | null;   // NEW — catch-up curve data
}
```

---

## 4. Module Permissions

In `entry/src/main/module.json5`, add required permissions:

```json5
{
  "requestPermissions": [
    {
      "name": "ohos.permission.ACCELEROMETER",
      "reason": "$string:health_monitoring_reason"
    },
    {
      "name": "ohos.permission.READ_HEALTH_DATA",
      "reason": "$string:health_monitoring_reason"
    },
    {
      "name": "ohos.permission.ACTIVITY_MOTION",
      "reason": "$string:health_monitoring_reason"
    },
    {
      "name": "ohos.permission.INTERNET"
      // already present for water tracking
    }
  ]
}
```

Add a string resource `health_monitoring_reason` =
`"Heart rate and sleep monitoring for health tracking"`.

---

## 5. Constraints & Edge Cases

1. **Battery**: HR sensor at 10-min intervals is already Huawei's
   recommended low-power cadence. Do NOT poll faster.
2. **No duplicate pushes**: Before pushing, check that the last push was
   ≥ 14 min ago (debounce). Store `lastHRPushTime` in preferences.
3. **No push when server disabled**: Check `StorageService.isServerEnabled()`
   before every push. If server sync is off, HR/sleep push is also off
   (regardless of the HR/sleep toggles).
4. **Graceful sensor unavailability**: Wrap `sensor.on()` in try-catch.
   If `HEART_RATE` sensor is not available, log a warning and set
   `hrEnabled = false` with a toast "HR sensor unavailable".
5. **Midnight rollover**: If the app is still running at midnight,
   clear `hrBuffer`. The server handles day boundaries.
6. **Test buttons**: The test payload should use `heart_rate: 0` so the
   server can distinguish test pushes. The server already accepts 0 values.
7. **Thread safety**: `hrBuffer` may be accessed from sensor callback
   and push timer concurrently. Use a simple mutex or copy-on-read.

---

## 6. What NOT to implement

- No new watch face / complication for HR or sleep.
- No HR history page on the watch.
- No sleep analysis on the watch (server does that).
- No vibration/notification for HR readings.
- No changes to the water tracking flow — it stays exactly as is.

---

## 7. Testing Checklist

- [ ] HR toggle on → sensor starts, push happens within 15 min
- [ ] HR toggle off → sensor stops, no more pushes
- [ ] Sleep toggle on → no visible change in main UI
- [ ] Test button → shows ✓ connected / ✗ failed within 3 sec
- [ ] Server disabled → HR/sleep pushes don't fire
- [ ] App restart → toggles restore, monitoring resumes if enabled
- [ ] Battery impact: < 5% per 8 hours with HR enabled
- [ ] Server receives `source: "watch"` in all health snapshots
- [ ] ServerResponse with new fields (velocity_warning, events_today,
      adaptive_curve) doesn't break existing water instruction parsing

---

## 8. Summary of API Changes Since Last WaterTracker Sync

These changes are already deployed on the server. Update the watch code
to be compatible:

1. **POST /api/water/report** now returns `{ status: "ok", instruction: { ... } }`
   — the full instruction is inline, no need to call GET /instruction separately.
2. **Instruction** now includes `velocity_warning` (string|null),
   `events_today` (int), and `adaptive_curve` (object|null).
3. **DELETE /api/water/intake/last** — new endpoint for undo.
4. **POST /api/health** — accepts `source: "watch"` (this is what you'll use).
5. **Behind-schedule suppression**: After >500 ml in 30 min, the server
   won't nag "du bist im Rückstand" — this is server-side only, no watch change needed.
