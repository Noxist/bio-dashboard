/**
 * IndexPage — horizontal swipe navigation: Hydration Curve | Tracking | Settings.
 *
 * Round 466 x 466 AMOLED (233 x 233 vp), r = 116.5 vp.
 * w(y) = 2 * sqrt(r^2 - (y - r)^2)
 *
 * Main panel height budget = 195 vp (centered: 19 vp margin each side).
 * Swiper indicator dots overlay at ~y=225, w~85 vp — no content overlap.
 *
 * @see https://developer.huawei.com/consumer/en/doc/best-practices/bpta-smartwatch
 */
import router from '@ohos.router';
import { Constants } from '../common/Constants';
import { StorageService } from '../service/StorageService';
import { HASyncService } from '../service/HASyncService';
import { ServerService } from '../service/ServerService';
import { DayLog, WaterModel, ServerResponse, HydrationCurveData, CurveTarget, CurvePoint } from '../model/WaterModel';

@Entry
@Component
struct IndexPage {
  // ── Main panel ──
  @State private currentIntake: number = 0;
  @State private dailyGoal: number = Constants.DEFAULT_DAILY_GOAL;
  @State private progress: number = 0;
  @State private entryCount: number = 0;
  @State private syncStatus: string = '';
  @State private selectedAmount: number = 250;
  @State private crownAccumulator: number = 0;
  @State private drinkSizes: number[] = [100, 250, 500];
  @State private serverMessage: string = '';
  @State private serverAmount: number = 0;
  @State private reminderMessage: string = '';

  // ── Hydration curve panel ──
  @State private curveData: HydrationCurveData | null = null;
  private curveCanvasSettings: RenderingContextSettings = new RenderingContextSettings(true);
  private curveCanvasCtx: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.curveCanvasSettings);
  @State private curveReady: boolean = false;

  // ── Settings panel ──
  @State private drinkSize1: number = Constants.DEFAULT_DRINK_SIZE_1;
  @State private drinkSize2: number = Constants.DEFAULT_DRINK_SIZE_2;
  @State private drinkSize3: number = Constants.DEFAULT_DRINK_SIZE_3;
  @State private syncEnabled: boolean = true;
  @State private serverEnabled: boolean = false;
  @State private reminderEnabled: boolean = false;
  @State private reminderInterval: number = Constants.DEFAULT_REMINDER_INTERVAL;
  @State private connectionStatus: string = '';

  // ── Navigation ──
  @State private activePanel: number = 1;
  private pollTimerId: number = -1;
  private reminderTimerId: number = -1;

  // ── Settings editing states ──
  @State private editingGoal: boolean = false;
  @State private editingDrinks: boolean = false;

  // ═══════════════════════════════════════════════════════════════
  // Lifecycle
  // ═══════════════════════════════════════════════════════════════

  aboutToAppear(): void {
    this.loadMainData();
    this.loadSettingsData();
    this.startTimers();
  }

  aboutToDisappear(): void {
    this.stopTimers();
  }

  onPageShow(): void {
    this.loadMainData();
    this.loadSettingsData();
    this.startTimers();
  }

  onPageHide(): void {
    this.stopTimers();
  }

  // ═══════════════════════════════════════════════════════════════
  // Data loading
  // ═══════════════════════════════════════════════════════════════

  private async loadMainData(): Promise<void> {
    this.dailyGoal = await StorageService.getDailyGoal();
    this.drinkSizes = await StorageService.getDrinkSizes();
    if (this.drinkSizes.indexOf(this.selectedAmount) < 0) {
      this.selectedAmount = this.drinkSizes[1];
    }
    const log: DayLog = await StorageService.getTodayLog();
    this.currentIntake = log.totalIntake;
    this.entryCount = log.entries.length;
    this.updateProgress();
  }

  private async loadCurveData(): Promise<void> {
    // Curve data comes from server poll; if not yet available, leave null
    if (this.curveData !== null && this.curveReady) {
      this.drawHydrationCurve();
    }
  }

  private async loadSettingsData(): Promise<void> {
    this.dailyGoal = await StorageService.getDailyGoal();
    this.syncEnabled = await StorageService.isHASyncEnabled();
    this.serverEnabled = await StorageService.isServerEnabled();
    this.reminderEnabled = await StorageService.isReminderEnabled();
    this.reminderInterval = await StorageService.getReminderInterval();
    const sizes: number[] = await StorageService.getDrinkSizes();
    this.drinkSize1 = sizes[0];
    this.drinkSize2 = sizes[1];
    this.drinkSize3 = sizes[2];
    this.drinkSizes = sizes;
  }

  // ═══════════════════════════════════════════════════════════════
  // Timers
  // ═══════════════════════════════════════════════════════════════

  private startTimers(): void {
    this.stopTimers();
    this.pollTimerId = setInterval(() => { this.pollServer(); }, Constants.SERVER_POLL_MS);
    this.pollServer();
    this.reminderTimerId = setInterval(() => { this.checkReminder(); }, Constants.REMINDER_CHECK_MS);
    this.checkReminder();
  }

  private stopTimers(): void {
    if (this.pollTimerId >= 0) { clearInterval(this.pollTimerId); this.pollTimerId = -1; }
    if (this.reminderTimerId >= 0) { clearInterval(this.reminderTimerId); this.reminderTimerId = -1; }
  }

  private async pollServer(): Promise<void> {
    const enabled: boolean = await StorageService.isServerEnabled();
    if (!enabled) { return; }
    try {
      await ServerService.reportStatus();
      const ins: ServerResponse | null = await ServerService.fetchInstruction();
      if (ins !== null) {
        if (ins.message.length > 0) {
          this.serverMessage = ins.message;
          this.serverAmount = ins.recommended_amount;
        }
        if (ins.daily_target_override > 0) {
          this.dailyGoal = ins.daily_target_override;
          StorageService.setDailyGoal(ins.daily_target_override);
          this.updateProgress();
        }
        // Store hydration curve data for the curve panel
        if (ins.hydration_curve !== null && ins.hydration_curve !== undefined) {
          this.curveData = ins.hydration_curve;
          if (this.curveReady) {
            this.drawHydrationCurve();
          }
        }
      }
    } catch (_e) { /* silent */ }
  }

  private async checkReminder(): Promise<void> {
    const enabled: boolean = await StorageService.isReminderEnabled();
    if (!enabled) { this.reminderMessage = ''; return; }
    const log: DayLog = await StorageService.getTodayLog();
    const interval: number = await StorageService.getReminderInterval();
    if (log.entries.length === 0) {
      this.reminderMessage = 'Time to hydrate!';
      return;
    }
    const lastTime: number = log.entries[log.entries.length - 1].timestamp;
    const elapsedMin: number = (Date.now() - lastTime) / 60000;
    this.reminderMessage = elapsedMin >= interval ? 'Time to drink!' : '';
  }

  // ═══════════════════════════════════════════════════════════════
  // Main panel actions
  // ═══════════════════════════════════════════════════════════════

  private updateProgress(): void {
    this.progress = this.dailyGoal > 0
      ? Math.min((this.currentIntake / this.dailyGoal) * 100, 100) : 0;
  }

  private async addWater(amount: number): Promise<void> {
    const log: DayLog = await StorageService.addWaterEntry(amount);
    this.currentIntake = log.totalIntake;
    this.entryCount = log.entries.length;
    this.updateProgress();
    this.reminderMessage = '';
    this.serverMessage = '';
    const isSyncEnabled: boolean = await StorageService.isHASyncEnabled();
    if (isSyncEnabled) {
      this.syncStatus = 'syncing';
      const ok: boolean = await HASyncService.syncToHA(log);
      this.syncStatus = ok ? 'synced' : 'offline';
      setTimeout(() => { this.syncStatus = ''; }, 2000);
    }
  }

  private async undoLast(): Promise<void> {
    if (this.entryCount === 0) { return; }
    const log: DayLog = await StorageService.undoLastEntry();
    this.currentIntake = log.totalIntake;
    this.entryCount = log.entries.length;
    this.updateProgress();
    HASyncService.syncToHA(log);
  }

  private getProgressColor(): string {
    if (this.progress >= 100) { return Constants.COLOR_SUCCESS; }
    if (this.progress >= 60) { return Constants.COLOR_ACCENT; }
    return Constants.COLOR_PRIMARY;
  }

  private cycleAmount(direction: number): void {
    const idx: number = this.drinkSizes.indexOf(this.selectedAmount);
    let next: number = idx < 0 ? 0 : idx + direction;
    if (next < 0) { next = this.drinkSizes.length - 1; }
    if (next >= this.drinkSizes.length) { next = 0; }
    this.selectedAmount = this.drinkSizes[next];
  }

  // ═══════════════════════════════════════════════════════════════
  // Settings panel actions
  // ═══════════════════════════════════════════════════════════════

  private adjustGoal(delta: number): void {
    const n: number = this.dailyGoal + delta;
    if (n >= 500 && n <= 5000) {
      this.dailyGoal = n;
      StorageService.setDailyGoal(n);
      this.updateProgress();
    }
  }

  private adjustSize(index: number, delta: number): void {
    const vals: number[] = [this.drinkSize1, this.drinkSize2, this.drinkSize3];
    const n: number = vals[index] + delta;
    if (n >= Constants.DRINK_SIZE_MIN && n <= Constants.DRINK_SIZE_MAX) {
      if (index === 0) { this.drinkSize1 = n; }
      if (index === 1) { this.drinkSize2 = n; }
      if (index === 2) { this.drinkSize3 = n; }
      StorageService.setDrinkSize(index, n);
      this.drinkSizes = [this.drinkSize1, this.drinkSize2, this.drinkSize3];
      if (this.selectedAmount === vals[index]) { this.selectedAmount = n; }
    }
  }

  private adjustReminder(delta: number): void {
    const n: number = this.reminderInterval + delta;
    if (n >= 15 && n <= 180) {
      this.reminderInterval = n;
      StorageService.setReminderInterval(n);
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // Hydration curve drawing
  // ═══════════════════════════════════════════════════════════════

  private drawHydrationCurve(): void {
    if (this.curveData === null) { return; }
    const ctx = this.curveCanvasCtx;
    const cw: number = 170;  // canvas width vp
    const ch: number = 88;   // canvas height vp
    const pad = { left: 2, right: 2, top: 6, bottom: 14 };
    const plotW: number = cw - pad.left - pad.right;
    const plotH: number = ch - pad.top - pad.bottom;
    const curve: HydrationCurveData = this.curveData;
    const wakeH: number = curve.wake_hour;
    const sleepH: number = curve.sleep_hour;
    const goalMl: number = curve.goal_ml > 0 ? curve.goal_ml : 1;

    // Coordinate transforms
    const hourToX = (hour: number): number => {
      return pad.left + ((hour - wakeH) / (sleepH - wakeH)) * plotW;
    };
    const mlToY = (ml: number): number => {
      return pad.top + plotH - (ml / goalMl) * plotH;
    };

    // Clear
    ctx.clearRect(0, 0, cw, ch);

    // Grid: subtle horizontal lines at 25%, 50%, 75%
    ctx.strokeStyle = '#1C1C1E';
    ctx.lineWidth = 0.5;
    ctx.setLineDash([]);
    for (let pct = 25; pct <= 75; pct += 25) {
      const gy: number = mlToY(goalMl * pct / 100);
      ctx.beginPath();
      ctx.moveTo(pad.left, gy);
      ctx.lineTo(pad.left + plotW, gy);
      ctx.stroke();
    }

    // Expected curve (dashed accent line)
    const pts: CurvePoint[] = curve.expected_curve;
    if (pts.length > 1) {
      ctx.strokeStyle = Constants.COLOR_TEXT_SECONDARY;
      ctx.lineWidth = 1.2;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(hourToX(pts[0].hour), mlToY(pts[0].ml));
      for (let i = 1; i < pts.length; i++) {
        ctx.lineTo(hourToX(pts[i].hour), mlToY(pts[i].ml));
      }
      ctx.stroke();
    }

    // Actual intake filled area (from wake to current hour)
    ctx.setLineDash([]);
    const curHour: number = curve.current_hour;
    const curMl: number = curve.current_ml;
    const curX: number = hourToX(curHour);
    const baseY: number = mlToY(0);

    // Fill area under actual intake
    ctx.fillStyle = 'rgba(79, 195, 247, 0.2)';
    ctx.beginPath();
    ctx.moveTo(hourToX(wakeH), baseY);
    ctx.lineTo(curX, baseY);
    ctx.lineTo(curX, mlToY(curMl));
    ctx.lineTo(hourToX(wakeH), mlToY(curMl));
    ctx.closePath();
    ctx.fill();

    // Actual intake line (solid primary)
    ctx.strokeStyle = Constants.COLOR_PRIMARY;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(hourToX(wakeH), mlToY(curMl));
    ctx.lineTo(curX, mlToY(curMl));
    ctx.stroke();

    // Current time vertical marker
    ctx.strokeStyle = Constants.COLOR_ACCENT;
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(curX, pad.top);
    ctx.lineTo(curX, baseY);
    ctx.stroke();

    // Target dots on the expected curve (15/30/45/60 min ahead)
    ctx.setLineDash([]);
    const targets: CurveTarget[] = curve.targets;
    for (let i = 0; i < targets.length; i++) {
      const t: CurveTarget = targets[i];
      const tHour: number = curHour + t.minutes / 60;
      if (tHour > sleepH) { continue; }
      const tx: number = hourToX(tHour);
      const ty: number = mlToY(t.target_ml);
      // Dot
      ctx.fillStyle = Constants.COLOR_ACCENT;
      ctx.beginPath();
      ctx.arc(tx, ty, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // Hour labels at bottom
    ctx.fillStyle = Constants.COLOR_TEXT_SECONDARY;
    ctx.font = '7vp sans-serif';
    ctx.textAlign = 'center';
    for (let hr = 8; hr <= 22; hr += 3) {
      ctx.fillText(String(hr), hourToX(hr), ch - 2);
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // Builder: Hydration Curve panel  (swipe left — replaces History)
  // ═══════════════════════════════════════════════════════════════

  @Builder hydrationCurvePanel() {
    Column() {
      // Title
      Text('Hydration')
        .fontSize(13)
        .fontWeight(FontWeight.Bold)
        .fontColor(Constants.COLOR_TEXT_PRIMARY)
        .margin({ bottom: 3 })

      if (this.curveData !== null) {
        // Status line: current vs expected
        Row() {
          Text(`${this.curveData.current_ml}`)
            .fontSize(11)
            .fontWeight(FontWeight.Bold)
            .fontColor(Constants.COLOR_PRIMARY)
          Text(` / ${this.curveData.current_expected_ml} ml`)
            .fontSize(9)
            .fontColor(Constants.COLOR_TEXT_SECONDARY)
        }
        .justifyContent(FlexAlign.Center)
        .margin({ bottom: 2 })

        // Canvas for the hydration curve
        Canvas(this.curveCanvasCtx)
          .width(170)
          .height(88)
          .backgroundColor(Constants.COLOR_BACKGROUND)
          .onReady(() => {
            this.curveReady = true;
            this.drawHydrationCurve();
          })

        // Interval target badges (15' / 30' / 45' / 1h)
        Row() {
          ForEach(this.curveData.targets, (t: CurveTarget) => {
            Column() {
              Text(t.label)
                .fontSize(7)
                .fontColor(Constants.COLOR_TEXT_SECONDARY)
              Text(`+${t.delta_ml}`)
                .fontSize(10)
                .fontWeight(FontWeight.Bold)
                .fontColor(
                  t.delta_ml === 0 ? Constants.COLOR_SUCCESS : Constants.COLOR_ACCENT
                )
              Text('ml')
                .fontSize(6)
                .fontColor(Constants.COLOR_TEXT_SECONDARY)
                .margin({ top: -1 })
            }
            .width(38)
            .height(36)
            .justifyContent(FlexAlign.Center)
            .backgroundColor(Constants.COLOR_SURFACE)
            .borderRadius(8)
          }, (t: CurveTarget) => t.label)
        }
        .width(170)
        .justifyContent(FlexAlign.SpaceBetween)
        .margin({ top: 4 })
      } else {
        // No curve data yet — show placeholder
        Column() {
          Text('⟳')
            .fontSize(24)
            .fontColor(Constants.COLOR_TEXT_SECONDARY)
            .margin({ top: 20 })
          Text('Waiting for server...')
            .fontSize(10)
            .fontColor(Constants.COLOR_TEXT_SECONDARY)
            .margin({ top: 6 })
          Text('Enable Health Server in settings')
            .fontSize(8)
            .fontColor(Constants.COLOR_TEXT_SECONDARY)
            .margin({ top: 2 })
        }
      }
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
    .backgroundColor(Constants.COLOR_BACKGROUND)
  }

  // ═══════════════════════════════════════════════════════════════
  // Builder: Main tracking panel  (center, default)
  // ═══════════════════════════════════════════════════════════════

  @Builder mainPanel() {
    Column() {
      // Sync indicator (10 vp)
      Text(this.syncStatus === 'syncing' ? '...'
        : this.syncStatus === 'synced' ? 'ok'
          : this.syncStatus === 'offline' ? '!'
            : ' ')
        .fontSize(9)
        .fontColor(
          this.syncStatus === 'synced' ? Constants.COLOR_SUCCESS
            : this.syncStatus === 'syncing' ? Constants.COLOR_PRIMARY
              : this.syncStatus === 'offline' ? Constants.COLOR_WARNING
                : Color.Transparent
        )
        .height(10)
        .textAlign(TextAlign.Center)

      // Progress ring (135 vp)
      Stack({ alignContent: Alignment.Center }) {
        Progress({ value: this.progress, total: 100, type: ProgressType.Ring })
          .width(135)
          .height(135)
          .color(this.getProgressColor())
          .backgroundColor(Constants.COLOR_PROGRESS_BG)
          .style({ strokeWidth: 10 })

        Column() {
          Text(`${this.currentIntake}`)
            .fontSize(30)
            .fontWeight(FontWeight.Bold)
            .fontColor(Constants.COLOR_TEXT_PRIMARY)
          Text('ml')
            .fontSize(10)
            .fontColor(Constants.COLOR_TEXT_SECONDARY)
            .margin({ top: -2 })
          Text(`/ ${this.dailyGoal}`)
            .fontSize(9)
            .fontColor(Constants.COLOR_TEXT_SECONDARY)
            .margin({ top: 1 })

          if (this.serverMessage !== '') {
            Text(this.serverMessage)
              .fontSize(7)
              .fontColor(Constants.COLOR_WARNING)
              .textAlign(TextAlign.Center)
              .maxLines(1)
              .textOverflow({ overflow: TextOverflow.Ellipsis })
              .constraintSize({ maxWidth: 80 })
              .margin({ top: 2 })
          } else if (this.reminderMessage !== '') {
            Text(this.reminderMessage)
              .fontSize(7)
              .fontColor(Constants.COLOR_PRIMARY)
              .textAlign(TextAlign.Center)
              .maxLines(1)
              .constraintSize({ maxWidth: 80 })
              .margin({ top: 2 })
          } else if (this.entryCount > 0) {
            Text('Undo')
              .fontSize(7)
              .fontColor(Constants.COLOR_TEXT_SECONDARY)
              .margin({ top: 2 })
              .onClick(() => { this.undoLast(); })
          }
        }
      }
      .onClick(() => {
        if (this.serverAmount > 0 && this.serverMessage !== '') {
          this.addWater(this.serverAmount);
        }
      })

      // Add button (34 vp)
      Button(`+ ${this.selectedAmount} ml`)
        .fontSize(12)
        .fontWeight(FontWeight.Bold)
        .fontColor(Constants.COLOR_BACKGROUND)
        .backgroundColor(Constants.COLOR_PRIMARY)
        .borderRadius(17)
        .height(34)
        .width(115)
        .margin({ top: 3 })
        .onClick(() => { this.addWater(this.selectedAmount); })

      // Amount selector (12 vp)
      Row() {
        ForEach(this.drinkSizes, (amt: number) => {
          Text(`${amt}`)
            .fontSize(9)
            .fontColor(this.selectedAmount === amt
              ? Constants.COLOR_PRIMARY
              : Constants.COLOR_TEXT_SECONDARY)
            .fontWeight(this.selectedAmount === amt
              ? FontWeight.Bold
              : FontWeight.Normal)
            .onClick(() => { this.selectedAmount = amt; })
            .padding({ left: 6, right: 6 })
        }, (amt: number) => amt.toString())
      }
      .justifyContent(FlexAlign.Center)
      .margin({ top: 2 })
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
    .backgroundColor(Constants.COLOR_BACKGROUND)
  }

  // ═══════════════════════════════════════════════════════════════
  // Builder: Settings panel  (swipe right)
  // ═══════════════════════════════════════════════════════════════

  @Builder settingIcon(icon: string, bgColor: string) {
    Row() {
      Text(icon)
        .fontSize(16)
        .fontColor('#FFFFFF')
    }
    .width(30)
    .height(30)
    .borderRadius(8)
    .backgroundColor(bgColor)
    .justifyContent(FlexAlign.Center)
    .margin({ right: 10 })
  }

  @Builder settingsPanel() {
    Column() {
      Scroll() {
        Column() {
          Text('Settings')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor(Constants.COLOR_TEXT_PRIMARY)
            .width('100%')
            .textAlign(TextAlign.Center)
            .margin({ bottom: 14 })

          // ═══ Daily Goal ═══
          Column() {
            Row() {
              this.settingIcon('◎', '#1565C0')

              Column() {
                Text('Daily Goal')
                  .fontSize(15)
                  .fontWeight(FontWeight.Medium)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                Text(`Goal: ${this.dailyGoal} ml`)
                  .fontSize(12)
                  .fontColor(Constants.COLOR_TEXT_SECONDARY)
                  .margin({ top: 2 })
              }
              .layoutWeight(1)
              .alignItems(HorizontalAlign.Start)

              Text(this.editingGoal ? '▾' : '›')
                .fontSize(20)
                .fontColor(Constants.COLOR_TEXT_SECONDARY)
            }
            .width('100%')
            .height(60)
            .padding({ left: 14, right: 14 })
            .alignItems(VerticalAlign.Center)
            .onClick(() => { this.editingGoal = !this.editingGoal; })

            if (this.editingGoal) {
              Divider()
                .color(Constants.COLOR_PROGRESS_BG)
                .margin({ left: 14, right: 14 })

              Row() {
                Button('−')
                  .fontSize(22)
                  .fontWeight(FontWeight.Bold)
                  .width(50)
                  .height(50)
                  .borderRadius(25)
                  .backgroundColor(Constants.COLOR_PROGRESS_BG)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  .onClick(() => { this.adjustGoal(-250); })

                Column() {
                  Text(`${this.dailyGoal}`)
                    .fontSize(26)
                    .fontWeight(FontWeight.Bold)
                    .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  Text('ml')
                    .fontSize(12)
                    .fontColor(Constants.COLOR_TEXT_SECONDARY)
                }
                .layoutWeight(1)

                Button('+')
                  .fontSize(22)
                  .fontWeight(FontWeight.Bold)
                  .width(50)
                  .height(50)
                  .borderRadius(25)
                  .backgroundColor(Constants.COLOR_PROGRESS_BG)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  .onClick(() => { this.adjustGoal(250); })
              }
              .width('100%')
              .padding({ left: 14, right: 14, top: 10, bottom: 14 })
              .justifyContent(FlexAlign.SpaceBetween)
            }
          }
          .backgroundColor(Constants.COLOR_SURFACE)
          .borderRadius(16)
          .margin({ bottom: 8 })
          .clip(true)

          // ═══ Drink Sizes ═══
          Column() {
            Row() {
              this.settingIcon('◆', '#0097A7')

              Column() {
                Text('Drink Sizes')
                  .fontSize(15)
                  .fontWeight(FontWeight.Medium)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                Text(`${this.drinkSize1} · ${this.drinkSize2} · ${this.drinkSize3} ml`)
                  .fontSize(12)
                  .fontColor(Constants.COLOR_TEXT_SECONDARY)
                  .margin({ top: 2 })
              }
              .layoutWeight(1)
              .alignItems(HorizontalAlign.Start)

              Text(this.editingDrinks ? '▾' : '›')
                .fontSize(20)
                .fontColor(Constants.COLOR_TEXT_SECONDARY)
            }
            .width('100%')
            .height(60)
            .padding({ left: 14, right: 14 })
            .alignItems(VerticalAlign.Center)
            .onClick(() => { this.editingDrinks = !this.editingDrinks; })

            if (this.editingDrinks) {
              Divider()
                .color(Constants.COLOR_PROGRESS_BG)
                .margin({ left: 14, right: 14 })

              Column() {
                // Size S
                Row() {
                  Text('S')
                    .fontSize(14)
                    .fontWeight(FontWeight.Medium)
                    .fontColor(Constants.COLOR_TEXT_SECONDARY)
                    .width(22)
                  Button('−')
                    .fontSize(18).fontWeight(FontWeight.Bold)
                    .width(42).height(42).borderRadius(21)
                    .backgroundColor(Constants.COLOR_PROGRESS_BG)
                    .fontColor(Constants.COLOR_TEXT_PRIMARY)
                    .onClick(() => { this.adjustSize(0, -Constants.DRINK_SIZE_STEP); })
                  Text(`${this.drinkSize1}`)
                    .fontSize(17).fontWeight(FontWeight.Bold)
                    .fontColor(Constants.COLOR_TEXT_PRIMARY)
                    .layoutWeight(1).textAlign(TextAlign.Center)
                  Button('+')
                    .fontSize(18).fontWeight(FontWeight.Bold)
                    .width(42).height(42).borderRadius(21)
                    .backgroundColor(Constants.COLOR_PROGRESS_BG)
                    .fontColor(Constants.COLOR_TEXT_PRIMARY)
                    .onClick(() => { this.adjustSize(0, Constants.DRINK_SIZE_STEP); })
                }
                .width('100%')
                .padding({ left: 14, right: 14, top: 6, bottom: 4 })
                .alignItems(VerticalAlign.Center)

                // Size M
                Row() {
                  Text('M')
                    .fontSize(14)
                    .fontWeight(FontWeight.Medium)
                    .fontColor(Constants.COLOR_TEXT_SECONDARY)
                    .width(22)
                  Button('−')
                    .fontSize(18).fontWeight(FontWeight.Bold)
                    .width(42).height(42).borderRadius(21)
                    .backgroundColor(Constants.COLOR_PROGRESS_BG)
                    .fontColor(Constants.COLOR_TEXT_PRIMARY)
                    .onClick(() => { this.adjustSize(1, -Constants.DRINK_SIZE_STEP); })
                  Text(`${this.drinkSize2}`)
                    .fontSize(17).fontWeight(FontWeight.Bold)
                    .fontColor(Constants.COLOR_TEXT_PRIMARY)
                    .layoutWeight(1).textAlign(TextAlign.Center)
                  Button('+')
                    .fontSize(18).fontWeight(FontWeight.Bold)
                    .width(42).height(42).borderRadius(21)
                    .backgroundColor(Constants.COLOR_PROGRESS_BG)
                    .fontColor(Constants.COLOR_TEXT_PRIMARY)
                    .onClick(() => { this.adjustSize(1, Constants.DRINK_SIZE_STEP); })
                }
                .width('100%')
                .padding({ left: 14, right: 14, top: 4, bottom: 4 })
                .alignItems(VerticalAlign.Center)

                // Size L
                Row() {
                  Text('L')
                    .fontSize(14)
                    .fontWeight(FontWeight.Medium)
                    .fontColor(Constants.COLOR_TEXT_SECONDARY)
                    .width(22)
                  Button('−')
                    .fontSize(18).fontWeight(FontWeight.Bold)
                    .width(42).height(42).borderRadius(21)
                    .backgroundColor(Constants.COLOR_PROGRESS_BG)
                    .fontColor(Constants.COLOR_TEXT_PRIMARY)
                    .onClick(() => { this.adjustSize(2, -Constants.DRINK_SIZE_STEP); })
                  Text(`${this.drinkSize3}`)
                    .fontSize(17).fontWeight(FontWeight.Bold)
                    .fontColor(Constants.COLOR_TEXT_PRIMARY)
                    .layoutWeight(1).textAlign(TextAlign.Center)
                  Button('+')
                    .fontSize(18).fontWeight(FontWeight.Bold)
                    .width(42).height(42).borderRadius(21)
                    .backgroundColor(Constants.COLOR_PROGRESS_BG)
                    .fontColor(Constants.COLOR_TEXT_PRIMARY)
                    .onClick(() => { this.adjustSize(2, Constants.DRINK_SIZE_STEP); })
                }
                .width('100%')
                .padding({ left: 14, right: 14, top: 4, bottom: 8 })
                .alignItems(VerticalAlign.Center)
              }
            }
          }
          .backgroundColor(Constants.COLOR_SURFACE)
          .borderRadius(16)
          .margin({ bottom: 8 })
          .clip(true)

          // ═══ Reminders ═══
          Column() {
            Row() {
              this.settingIcon('♪', '#E65100')

              Text('Reminders')
                .fontSize(15)
                .fontWeight(FontWeight.Medium)
                .fontColor(Constants.COLOR_TEXT_PRIMARY)
                .layoutWeight(1)

              Toggle({ type: ToggleType.Switch, isOn: this.reminderEnabled })
                .selectedColor(Constants.COLOR_PRIMARY)
                .onChange((isOn: boolean) => {
                  this.reminderEnabled = isOn;
                  StorageService.setReminderEnabled(isOn);
                })
            }
            .width('100%')
            .height(60)
            .padding({ left: 14, right: 14 })
            .alignItems(VerticalAlign.Center)

            if (this.reminderEnabled) {
              Divider()
                .color(Constants.COLOR_PROGRESS_BG)
                .margin({ left: 14, right: 14 })

              Row() {
                Button('−')
                  .fontSize(20).fontWeight(FontWeight.Bold)
                  .width(46).height(46).borderRadius(23)
                  .backgroundColor(Constants.COLOR_PROGRESS_BG)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  .onClick(() => { this.adjustReminder(-15); })

                Column() {
                  Text(`${this.reminderInterval}`)
                    .fontSize(22)
                    .fontWeight(FontWeight.Bold)
                    .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  Text('minutes')
                    .fontSize(11)
                    .fontColor(Constants.COLOR_TEXT_SECONDARY)
                }
                .layoutWeight(1)

                Button('+')
                  .fontSize(20).fontWeight(FontWeight.Bold)
                  .width(46).height(46).borderRadius(23)
                  .backgroundColor(Constants.COLOR_PROGRESS_BG)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  .onClick(() => { this.adjustReminder(15); })
              }
              .width('100%')
              .padding({ left: 14, right: 14, top: 8, bottom: 12 })
              .justifyContent(FlexAlign.SpaceBetween)
            }
          }
          .backgroundColor(Constants.COLOR_SURFACE)
          .borderRadius(16)
          .margin({ bottom: 8 })
          .clip(true)

          // ═══ HA Sync ═══
          Column() {
            Row() {
              this.settingIcon('⇄', '#2E7D32')

              Text('HA Sync')
                .fontSize(15)
                .fontWeight(FontWeight.Medium)
                .fontColor(Constants.COLOR_TEXT_PRIMARY)
                .layoutWeight(1)

              Toggle({ type: ToggleType.Switch, isOn: this.syncEnabled })
                .selectedColor(Constants.COLOR_PRIMARY)
                .onChange((isOn: boolean) => {
                  this.syncEnabled = isOn;
                  StorageService.setHASyncEnabled(isOn);
                })
            }
            .width('100%')
            .height(60)
            .padding({ left: 14, right: 14 })
            .alignItems(VerticalAlign.Center)

            if (this.syncEnabled) {
              Divider()
                .color(Constants.COLOR_PROGRESS_BG)
                .margin({ left: 14, right: 14 })

              Button('Test Connection')
                .fontSize(13)
                .fontWeight(FontWeight.Medium)
                .height(42)
                .borderRadius(21)
                .backgroundColor(Constants.COLOR_PROGRESS_BG)
                .fontColor(Constants.COLOR_TEXT_PRIMARY)
                .width('80%')
                .margin({ top: 8, bottom: 10 })
                .onClick(async () => {
                  this.connectionStatus = 'Testing...';
                  const result = await HASyncService.testConnection();
                  this.connectionStatus = result.success ? '✓ Connected' : result.message;
                  setTimeout(() => { this.connectionStatus = ''; }, 3000);
                })

              if (this.connectionStatus !== '') {
                Text(this.connectionStatus)
                  .fontSize(12)
                  .fontColor(
                    this.connectionStatus.startsWith('✓')
                      ? Constants.COLOR_SUCCESS
                      : Constants.COLOR_WARNING
                  )
                  .margin({ bottom: 8 })
                  .textAlign(TextAlign.Center)
                  .width('100%')
              }
            }
          }
          .backgroundColor(Constants.COLOR_SURFACE)
          .borderRadius(16)
          .margin({ bottom: 8 })
          .clip(true)

          // ═══ Health Server ═══
          Row() {
            this.settingIcon('⬡', '#546E7A')

            Text('Health Server')
              .fontSize(15)
              .fontWeight(FontWeight.Medium)
              .fontColor(Constants.COLOR_TEXT_PRIMARY)
              .layoutWeight(1)

            Toggle({ type: ToggleType.Switch, isOn: this.serverEnabled })
              .selectedColor(Constants.COLOR_PRIMARY)
              .onChange((isOn: boolean) => {
                this.serverEnabled = isOn;
                StorageService.setServerEnabled(isOn);
              })
          }
          .width('100%')
          .height(60)
          .padding({ left: 14, right: 14 })
          .alignItems(VerticalAlign.Center)
          .backgroundColor(Constants.COLOR_SURFACE)
          .borderRadius(16)
          .margin({ bottom: 8 })

          // ═══ Manage Entries ═══
          Row() {
            this.settingIcon('☰', '#6A1B9A')

            Text('Manage Entries')
              .fontSize(15)
              .fontWeight(FontWeight.Medium)
              .fontColor(Constants.COLOR_TEXT_PRIMARY)
              .layoutWeight(1)

            Text('›')
              .fontSize(22)
              .fontColor(Constants.COLOR_TEXT_SECONDARY)
          }
          .width('100%')
          .height(60)
          .padding({ left: 14, right: 14 })
          .alignItems(VerticalAlign.Center)
          .backgroundColor(Constants.COLOR_SURFACE)
          .borderRadius(16)
          .margin({ bottom: 12 })
          .onClick(() => { router.pushUrl({ url: 'pages/ManageEntriesPage' }); })
        }
        .width('100%')
        .padding({
          left: Constants.MARGIN_LEFT,
          right: Constants.MARGIN_RIGHT,
          top: Constants.PADDING_CONTENT_TOP,
          bottom: Constants.PADDING_CONTENT_BOTTOM
        })
      }
      .width('100%')
      .layoutWeight(1)
      .scrollBar(BarState.Off)
    }
    .width('100%')
    .height('100%')
    .backgroundColor(Constants.COLOR_BACKGROUND)
  }

  // ═══════════════════════════════════════════════════════════════
  // Build: Swiper with 3 panels
  // ═══════════════════════════════════════════════════════════════

  build() {
    Swiper() {
      this.hydrationCurvePanel()
      this.mainPanel()
      this.settingsPanel()
    }
    .index(1)
    .loop(false)
    .indicator(true)
    .backgroundColor(Constants.COLOR_BACKGROUND)
    .onChange((index: number) => {
      this.activePanel = index;
      if (index === 0) { this.loadCurveData(); }
      if (index === 1) { this.loadMainData(); }
      if (index === 2) { this.loadSettingsData(); }
    })
    .onDigitalCrown((event: CrownEvent) => {
      event.stopPropagation();
      this.crownAccumulator += event.degree;
      if (this.activePanel === 1) {
        if (this.crownAccumulator > 15) { this.cycleAmount(1); this.crownAccumulator = 0; }
        else if (this.crownAccumulator < -15) { this.cycleAmount(-1); this.crownAccumulator = 0; }
      } else if (this.activePanel === 2) {
        if (this.crownAccumulator > 15) { this.adjustGoal(250); this.crownAccumulator = 0; }
        else if (this.crownAccumulator < -15) { this.adjustGoal(-250); this.crownAccumulator = 0; }
      }
    })
  }
}
