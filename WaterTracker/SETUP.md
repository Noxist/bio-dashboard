# Water Tracker for Huawei Watch Ultimate 2 -- Setup Guide

Complete setup instructions for building the HarmonyOS watch app, connecting
it to Home Assistant, and optionally bridging data to Google Fit.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install DevEco Studio](#2-install-deveco-studio)
3. [Open and Configure the Project](#3-open-and-configure-the-project)
4. [Create an App Icon](#4-create-an-app-icon)
5. [Enable Developer Mode on the Watch](#5-enable-developer-mode-on-the-watch)
6. [Connect DevEco Studio to the Watch](#6-connect-deveco-studio-to-the-watch)
7. [Build and Deploy](#7-build-and-deploy)
8. [Home Assistant Setup](#8-home-assistant-setup)
9. [Configure the Watch App](#9-configure-the-watch-app)
10. [Google Fit Bridge (Optional)](#10-google-fit-bridge-optional)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prerequisites

| Item | Details |
|------|---------|
| **Huawei Developer account** | Already verified (you confirmed this). |
| **Huawei Watch Ultimate 2** | Running HarmonyOS 4.0 or later. |
| **Android phone** | Paired via the Huawei Health app. |
| **PC** | Windows 10/11, 16 GB RAM recommended. |
| **Home Assistant** | Accessible via Nabu Casa (`https://xxxxx.ui.nabu.casa`). |

---

## 2. Install DevEco Studio

1. Download **DevEco Studio 4.1** (or the latest 4.x release) from
   <https://developer.huawei.com/consumer/en/deveco-studio/>.
2. Run the installer. Accept defaults.
3. On first launch, the IDE will ask you to install SDKs.  Install:
   - **HarmonyOS SDK, API 10** (or latest available for wearable).
   - Check "Wearable" under device types in the SDK Manager.
4. If prompted for the HarmonyOS toolchain (hvigor), let the IDE download it
   automatically.

> **Tip:** If the SDK Manager shows API 12 (HarmonyOS NEXT) as the latest,
> install it *alongside* API 10.  The project's `build-profile.json5`
> targets `compatibleSdkVersion: "4.0.0(10)"`, so API 10 is needed.

---

## 3. Open and Configure the Project

1. Launch DevEco Studio.
2. **File > Open** and select the `Water Tracker` folder (this repository root).
3. The IDE will detect the `build-profile.json5` and configure the project.
4. Wait for Gradle / hvigor sync to complete (bottom status bar).
5. If the IDE complains about a missing SDK path, go to
   **File > Project Structure > SDK** and point it to your installed SDK.

### Signing Configuration

To deploy to a real watch you need a signing certificate:

1. **File > Project Structure > Signing Configs**.
2. Check **Automatically generate signing** (requires your Huawei ID login).
3. DevEco Studio will create a debug certificate and provision profile.
4. The generated signing config is written into `build-profile.json5`
   automatically.

---

## 4. Create an App Icon

The project references `$media:app_icon` but does not ship a PNG.  Place a
square PNG (preferably 216 x 216 px) at:

```
entry/src/main/resources/base/media/app_icon.png
```

A simple coloured water-drop icon works well.  You can generate one with
any image editor or use an AI image generator.

---

## 5. Enable Developer Mode on the Watch

1. On the watch: **Settings > About > Software version**.
2. Tap **Software version** rapidly 7 times.
3. You will see a toast "Developer mode enabled" (or similar).
4. Go back to **Settings > Developer options**.
5. Enable **USB debugging** or **Wireless debugging** (depending on firmware).

> The Watch Ultimate 2 uses Bluetooth-based debugging through the phone
> *or* WiFi debugging when watch and PC are on the same network.

---

## 6. Connect DevEco Studio to the Watch

### Option A -- WiFi debugging (recommended)

1. On the watch: **Settings > Developer options > Wireless debugging**.
2. Note the watch's IP address and port.
3. In DevEco Studio's terminal:
   ```
   hdc tconn <watch-ip>:<port>
   ```
4. The watch will show a pairing prompt. Accept it.
5. Verify: `hdc list targets` should list the watch.

### Option B -- via phone relay (Bluetooth)

1. Open **Huawei Health** on your Android phone.
2. Ensure the watch is paired and connected.
3. In DevEco Studio, the watch may appear as a remote device.
   Follow the IDE's prompts to authorise.

> `hdc` is Huawei's equivalent of Android's `adb`.  It ships with the
> HarmonyOS SDK under `{sdk}/toolchains/`.

---

## 7. Build and Deploy

1. In DevEco Studio, select **entry** module and choose the connected
   watch as the target device.
2. Click **Run > Run 'entry'** (or press Shift+F10).
3. The IDE builds a `.hap` file and installs it on the watch.
4. The app should launch automatically and show the main water tracking
   screen.

### Manual install via command line

```bash
cd "c:\coding\Water Tracker"
# Build
hvigor assembleHap --mode module -p module=entry

# The HAP is output to:
#   entry/build/default/outputs/default/entry-default-signed.hap

# Install
hdc install entry/build/default/outputs/default/entry-default-signed.hap
```

---

## 8. Home Assistant Setup

### 8.1. Create a Long-Lived Access Token

1. In your HA web UI, click your profile avatar (bottom-left).
2. Scroll to **Long-Lived Access Tokens**.
3. Click **Create Token**, name it `Water Tracker`, and copy the token.
   Store it somewhere safe -- you will enter it on the watch.

### 8.2. Install the Package (optional but recommended)

The file `homeassistant/water_tracker_package.yaml` provides template
sensors, automations (hydration reminders), and a Lovelace card suggestion.

1. In your HA config directory, create a `packages` folder if it does not
   exist.
2. Copy `water_tracker_package.yaml` into `packages/`.
3. Make sure your `configuration.yaml` includes:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
4. Restart Home Assistant (**Developer Tools > Restart**).

After the watch sends its first reading, `sensor.water_tracker_daily` will
appear automatically (the REST API creates it on the fly).

---

## 9. Configure the Watch App

1. Open the Water Tracker app on the watch.
2. Tap **Setup** at the bottom.
3. Toggle **HA Sync** on.
4. Enter your Nabu Casa URL (e.g. `https://abcdef123.ui.nabu.casa`).
   - Voice input is usually fastest on the watch -- long-press the
     microphone icon on the keyboard.
5. Enter the Long-Lived Access Token.
6. Tap **Save**, then **Test**.  You should see "Connected!".
7. Go back to the main screen and tap **+250** to test.  The sync status
   chip at the top should briefly show "Syncing..." then "Synced".

### Pre-configuring via code (developer shortcut)

If typing on the watch is too painful, you can hardcode the defaults
during development.  In `entry/src/main/ets/common/Constants.ets`, add:

```typescript
static readonly DEFAULT_HA_URL: string = 'https://YOUR_NABU_CASA_URL';
static readonly DEFAULT_HA_TOKEN: string = 'YOUR_TOKEN_HERE';
static readonly DEFAULT_HA_SYNC_ENABLED: boolean = true;
```

Then update `StorageService.ets` to use those defaults in the `get*`
methods.  Remove the hardcoded values before publishing.

---

## 10. Google Fit Bridge (Optional)

Because the Huawei Watch runs HarmonyOS (not Wear OS), there is no native
path to Google Fit.  The bridge works like this:

```
Watch  -->  Home Assistant  -->  Python script  -->  Google Fit REST API
```

The HA companion app on your Android phone can then read the Google Fit
hydration data and surface it as an HA sensor, closing the loop.

### 10.1. Google Cloud setup

1. Go to <https://console.cloud.google.com>.
2. Create a project (or reuse an existing one).
3. **APIs & Services > Enable APIs** -- enable **Fitness API**.
4. **APIs & Services > Credentials > Create Credentials > OAuth Client ID**.
   - Application type: **Desktop app**.
   - Download the JSON and save it as `scripts/credentials.json`.

### 10.2. First run (interactive)

```bash
cd scripts
pip install -r requirements.txt

# Set HA connection
export HA_URL="https://xxxxx.ui.nabu.casa"
export HA_TOKEN="eyJ0eX..."

python google_fit_sync.py
```

A browser window will open for Google consent.  Approve the
`fitness.nutrition` scopes.  A `token.json` is cached for future runs.

### 10.3. Automate

#### Cron (Linux / WSL)

```cron
*/15 * * * * cd /path/to/scripts && HA_URL="..." HA_TOKEN="..." python3 google_fit_sync.py >> /var/log/water_fit_sync.log 2>&1
```

#### Home Assistant shell_command

```yaml
shell_command:
  sync_water_to_google_fit: >
    cd /config/scripts/water_tracker &&
    HA_URL="{{ states('input_text.ha_url') }}"
    HA_TOKEN="{{ states('input_text.ha_token') }}"
    python3 google_fit_sync.py
```

Then trigger it via an automation whenever `sensor.water_tracker_daily`
changes.

### 10.4. Future-proofing

Google has deprecated the Fitness REST API in favour of Health Connect
(Android 14+).  If the REST API stops working:

- Build a small Kotlin Android app that reads
  `sensor.water_tracker_daily` from HA and writes to Health Connect's
  `HydrationRecord`.  The HA Companion app and Google Fit will both see it.
- Or use Tasker + Health Connect Plugin on Android as a no-code solution.

---

## 11. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `hdc list targets` shows nothing | Ensure WiFi debugging is enabled on the watch and both devices are on the same network.  Restart `hdc` with `hdc kill` then `hdc start`. |
| Build fails: "API version not supported" | Open SDK Manager and install API 10.  Ensure `compatibleSdkVersion` in `build-profile.json5` matches. |
| App crashes on launch | Check HiLog in DevEco Studio.  Most likely cause: `StorageService.init()` not awaited, or a missing resource file. |
| Sync shows "Offline" | Verify the watch has network (WiFi or BT tethering through phone).  Test the HA URL in a browser first. |
| HA entity not appearing | The entity is created on the first successful POST.  Check **Developer Tools > States** and search for `water_tracker`. |
| Google Fit script 403 | The Fitness API may not be enabled in your GCP project, or the OAuth token expired.  Delete `token.json` and re-auth. |
| Text input impossible on watch | Use the developer shortcut (hardcode values in Constants.ets) or use voice input via the watch keyboard's microphone button. |

---

## Architecture Summary

```
+----------------------------+
|  Huawei Watch Ultimate 2   |
|  (HarmonyOS 4 / ArkTS)    |
|                            |
|  Water Tracker App         |
|  - Circular progress UI    |
|  - Quick-add buttons       |
|  - Local preferences store |
|  - HTTP client             |
+-----------+----------------+
            |
            | POST /api/states/sensor.water_tracker_daily
            | (via phone BT tethering or WiFi)
            v
+-----------+----------------+
|  Home Assistant            |
|  (Nabu Casa cloud)        |
|                            |
|  - sensor entity           |
|  - template sensors        |
|  - reminder automations    |
|  - Lovelace dashboard      |
+-----------+----------------+
            |
            | Python bridge script (cron / HA automation)
            v
+-----------+----------------+
|  Google Fit REST API       |
|  com.google.hydration      |
+----------------------------+
```

---

## File Structure

```
Water Tracker/
|-- AppScope/                        # App-level config
|   |-- app.json5
|   +-- resources/base/element/string.json
|
|-- entry/                           # Main (and only) HAP module
|   |-- src/main/
|   |   |-- module.json5             # Module manifest (wearable)
|   |   |-- ets/
|   |   |   |-- entryability/EntryAbility.ets
|   |   |   |-- pages/
|   |   |   |   |-- IndexPage.ets    # Main tracker screen
|   |   |   |   |-- HistoryPage.ets  # 7-day bar chart
|   |   |   |   +-- SettingsPage.ets # Goal + HA config
|   |   |   |-- common/Constants.ets
|   |   |   |-- model/WaterModel.ets
|   |   |   +-- service/
|   |   |       |-- StorageService.ets
|   |   |       +-- HASyncService.ets
|   |   +-- resources/
|   |       +-- base/
|   |           |-- element/string.json, color.json
|   |           |-- media/app_icon.png   <-- YOU provide this
|   |           +-- profile/main_pages.json
|   |-- build-profile.json5
|   |-- hvigorfile.ts
|   +-- oh-package.json5
|
|-- homeassistant/
|   +-- water_tracker_package.yaml   # HA package (sensors, automations)
|
|-- scripts/
|   |-- google_fit_sync.py           # HA -> Google Fit bridge
|   |-- requirements.txt
|   +-- credentials.json             <-- YOU provide this (from GCP)
|
|-- build-profile.json5              # Root project build config
|-- hvigorfile.ts
|-- oh-package.json5
+-- SETUP.md                         # This file
```
