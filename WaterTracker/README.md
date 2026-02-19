# WaterTracker — HarmonyOS Watch App

A water intake tracker for Huawei Watch Ultimate 2 (HarmonyOS NEXT, API 21), with Home Assistant integration and a remote health monitoring server interface.

## Project Structure

```
entry/src/main/ets/
├── common/
│   └── Constants.ets            # App-wide constants, HA credentials, server config
├── entryability/
│   └── EntryAbility.ets         # App entry point, initialises StorageService
├── model/
│   └── WaterModel.ets           # Data models (WaterEntry, DayLog, ServerResponse)
├── pages/
│   ├── IndexPage.ets            # Main screen: progress ring, add water, reminders
│   ├── HistoryPage.ets          # 7-day intake history bar chart
│   ├── SettingsPage.ets         # All settings (goal, sizes, reminders, HA, server)
│   └── ManageEntriesPage.ets    # View and delete today's entries
└── service/
    ├── StorageService.ets       # Local persistence (@ohos.data.preferences)
    ├── HASyncService.ets        # Home Assistant REST API sync
    └── ServerService.ets        # Remote health monitoring server client
```

## Features

### Core Tracking
- **Progress ring** showing daily intake vs. goal on the main screen
- **3 configurable quick-add sizes** (default: 100 / 250 / 500 ml, adjustable in 25 ml steps)
- **Crown rotation** cycles through the drink sizes
- **Undo** last entry from the main screen
- **Entry management** page to view and delete individual entries
- **7-day history** with horizontal bar chart

### Configurable Settings (on-watch)
| Setting | Range | Step | Default |
|---|---|---|---|
| Daily goal | 500 – 5000 ml | 250 ml | 2500 ml |
| Drink size S | 25 – 1000 ml | 25 ml | 100 ml |
| Drink size M | 25 – 1000 ml | 25 ml | 250 ml |
| Drink size L | 25 – 1000 ml | 25 ml | 500 ml |
| Reminder interval | 15 – 180 min | 15 min | 60 min |

### Dehydration Reminders
When enabled in Settings → Reminders, the app checks every 60 seconds whether the time since the last water entry exceeds your configured interval. If it does, a **Time to drink!** banner appears on the main screen.

### Home Assistant Integration
Pushes water intake to a HA sensor entity (`sensor.water_tracker_daily`) via the REST API. Works with Nabu Casa or any exposed HA instance.

**Sensor attributes pushed:**
| Attribute | Description |
|---|---|
| `state` | Total daily intake (ml) |
| `unit_of_measurement` | `ml` |
| `entry_count` | Number of drinks logged today |
| `last_entry_amount` | ml of the most recent drink |
| `last_entry_time` | ISO 8601 timestamp of last drink |
| `daily_goal` | Current daily target |
| `goal_reached` | `true` when target has been met |

### Remote Health Monitoring Server
The watch can **periodically poll a remote server** (e.g., on Hetzner) to:
1. **Report** its current hydration state every 15 minutes
2. **Receive** personalised drinking instructions

This enables use cases like:
- "Bitte trinke 250 ml in den nächsten 30 Minuten"
- "Du bist 500 ml im Rückstand — trink mehr!"
- Dynamic daily goal adjustment based on activity/weather/health data

Tapping the instruction banner on the watch **auto-adds the recommended amount**.

---

## Server API Contract

The watch communicates with two endpoints. Authentication is via Bearer token.

### 1. Report Status — `POST /api/water/report`

The watch sends its current hydration status every 15 minutes (configurable via `Constants.SERVER_POLL_MS`).

**Request:**
```http
POST https://your-server.com/api/water/report
Authorization: Bearer <token>
Content-Type: application/json

{
  "device_id": "watch_ultra2",
  "current_intake": 1500,
  "daily_goal": 2500,
  "entry_count": 6,
  "last_drink_time": "2026-02-18T14:30:00.000Z",
  "timestamp": "2026-02-18T15:00:00.000Z"
}
```

**Expected response:** Any `2xx` status code.

### 2. Get Instruction — `GET /api/water/instruction`

After reporting, the watch queries for the latest drinking instruction.

**Request:**
```http
GET https://your-server.com/api/water/instruction?current_intake=1500&daily_goal=2500&last_drink_time=2026-02-18T14%3A30%3A00.000Z
Authorization: Bearer <token>
```

**Query parameters:**
| Parameter | Type | Description |
|---|---|---|
| `current_intake` | number | Total ml consumed today |
| `daily_goal` | number | Daily target in ml |
| `last_drink_time` | string | ISO 8601 timestamp of last drink (URL-encoded) |

**Response (JSON):**
```json
{
  "message": "Bitte trinke 250ml in den nächsten 30 Minuten",
  "recommended_amount": 250,
  "priority": "normal",
  "deadline_minutes": 30,
  "daily_target_override": 0,
  "timestamp": "2026-02-18T15:00:00.000Z"
}
```

**Response fields:**
| Field | Type | Description |
|---|---|---|
| `message` | string | Text displayed on the watch. Empty string = no instruction. |
| `recommended_amount` | number | Suggested amount in ml. Tapping the banner adds this. |
| `priority` | string | `"none"`, `"low"`, `"normal"`, `"high"`, or `"critical"` |
| `deadline_minutes` | number | Minutes until instruction expires. 0 = no deadline. |
| `daily_target_override` | number | Override daily goal on watch. 0 = no override. |
| `timestamp` | string | Server timestamp (ISO 8601). |

### Data Flow Diagram

```
┌──────────────┐   POST /api/water/report    ┌─────────────────────┐
│              │ ──────────────────────────►  │                     │
│  Watch App   │                              │   Hetzner Server    │
│  (IndexPage) │  GET /api/water/instruction  │   (health_server.py)│
│              │ ◄──────────────────────────  │                     │
└──────┬───────┘                              └──────────┬──────────┘
       │                                                 │
       │  POST /api/states/sensor.water_tracker_daily    │ Can also read
       ▼                                                 │ from HA API
┌──────────────┐                                         │
│ Home         │ ◄───────────────────────────────────────┘
│ Assistant    │
└──────────────┘
```

---

## Configuration

### Home Assistant
HA URL and long-lived access token are set in `Constants.ets`:
```typescript
public static readonly DEFAULT_HA_URL: string = 'https://your-instance.ui.nabu.casa';
public static readonly DEFAULT_HA_TOKEN: string = 'your-long-lived-access-token';
```
Toggle HA sync on/off in Settings on the watch.

### Health Monitoring Server
Set the server URL and token in `Constants.ets`:
```typescript
public static readonly DEFAULT_SERVER_URL: string = 'https://your-hetzner-server.com';
public static readonly DEFAULT_SERVER_TOKEN: string = 'your-api-token';
```
Then enable the **Server** toggle in Settings on the watch.

The server URL cannot be typed on the watch (no keyboard). Change it in `Constants.ets` and rebuild, or set it via ADB:
```bash
# Future: set via preferences if a companion phone app is added
```

### Polling Interval
Default: 15 minutes. Change in `Constants.ets`:
```typescript
public static readonly SERVER_POLL_MS: number = 900000; // milliseconds
```

---

## Example Server Implementation

A minimal Python/Flask server is included at `scripts/health_server.py`:

```bash
cd scripts
pip install -r requirements.txt
python health_server.py
```

The example server:
- Stores the latest watch report in memory
- Calculates expected intake based on time of day (16 waking hours)
- Returns a "drink more" instruction if the user is behind schedule
- Returns a reminder if >90 minutes since last drink

You can extend this to:
- Store data in a database (PostgreSQL, SQLite, InfluxDB)
- Integrate with other health APIs (Google Fit, Apple Health via proxy)
- Use weather data to adjust hydration targets
- Apply ML models for personalised hydration coaching
- Read data from Home Assistant to factor in activity/heart rate

---

## Build & Deploy

```powershell
# Build
cd C:\coding\WaterTracker
$env:DEVECO_SDK_HOME = "C:\Program Files\Huawei\DevEco Studio\sdk"
hvigorw.bat assembleHap --mode module -p product=default -p module=entry@default

# Connect to watch (find port via Settings > About > Developer options)
hdc tconn <WATCH_IP>:<PORT>

# Install
hdc install "entry\build\default\outputs\default\entry-default-signed.hap"
```

## Watch Specifications
- **Device**: Huawei Watch Ultimate 2
- **Display**: 1.5" round LTPO 2.0 AMOLED, 466 × 466 px (233 × 233 vp)
- **Platform**: HarmonyOS NEXT, API 21
- **Interaction**: Touch + Digital Crown rotation
- **Theme**: Pure black (#000000) background for AMOLED power efficiency
# WaterTracker
