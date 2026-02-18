/**
 * SettingsPage — full-screen settings for the Water Tracker.
 *
 * Large tappable cards optimized for the round Huawei Watch Ultimate 2
 * (466 × 466 px = 233 × 233 vp). Each setting is a prominent card with
 * an icon, title, subtitle, and an inline expandable editor with big
 * touch targets. Scroll vertically to reach all settings.
 *
 * @see https://developer.huawei.com/consumer/en/doc/design-guides/spacing-parameters-0000002202912577
 */
import router from '@ohos.router';
import { Constants } from '../common/Constants';
import { StorageService } from '../service/StorageService';
import { HASyncService } from '../service/HASyncService';

@Entry
@Component
struct SettingsPage {
  @State private dailyGoal: number = Constants.DEFAULT_DAILY_GOAL;
  @State private drinkSize1: number = Constants.DEFAULT_DRINK_SIZE_1;
  @State private drinkSize2: number = Constants.DEFAULT_DRINK_SIZE_2;
  @State private drinkSize3: number = Constants.DEFAULT_DRINK_SIZE_3;
  @State private syncEnabled: boolean = true;
  @State private serverEnabled: boolean = false;
  @State private serverUrl: string = '';
  @State private reminderEnabled: boolean = false;
  @State private reminderInterval: number = Constants.DEFAULT_REMINDER_INTERVAL;
  @State private connectionStatus: string = '';
  @State private editingGoal: boolean = false;
  @State private editingDrinks: boolean = false;

  aboutToAppear(): void {
    this.loadSettings();
  }

  private async loadSettings(): Promise<void> {
    this.dailyGoal = await StorageService.getDailyGoal();
    this.syncEnabled = await StorageService.isHASyncEnabled();
    this.serverEnabled = await StorageService.isServerEnabled();
    this.serverUrl = await StorageService.getServerUrl();
    this.reminderEnabled = await StorageService.isReminderEnabled();
    this.reminderInterval = await StorageService.getReminderInterval();
    const sizes: number[] = await StorageService.getDrinkSizes();
    this.drinkSize1 = sizes[0];
    this.drinkSize2 = sizes[1];
    this.drinkSize3 = sizes[2];
  }

  private adjustGoal(delta: number): void {
    const next: number = this.dailyGoal + delta;
    if (next >= 500 && next <= 5000) {
      this.dailyGoal = next;
      StorageService.setDailyGoal(this.dailyGoal);
    }
  }

  private adjustSize(index: number, delta: number): void {
    const values: number[] = [this.drinkSize1, this.drinkSize2, this.drinkSize3];
    const next: number = values[index] + delta;
    if (next >= Constants.DRINK_SIZE_MIN && next <= Constants.DRINK_SIZE_MAX) {
      if (index === 0) { this.drinkSize1 = next; }
      if (index === 1) { this.drinkSize2 = next; }
      if (index === 2) { this.drinkSize3 = next; }
      StorageService.setDrinkSize(index, next);
    }
  }

  private adjustReminder(delta: number): void {
    const next: number = this.reminderInterval + delta;
    if (next >= 15 && next <= 180) {
      this.reminderInterval = next;
      StorageService.setReminderInterval(next);
    }
  }

  // ── Reusable icon badge for setting rows ──
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

  build() {
    Scroll() {
      Column() {
        // ── Title (safe area for round screen top) ──
        Text('Settings')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .fontColor(Constants.COLOR_TEXT_PRIMARY)
          .width('100%')
          .textAlign(TextAlign.Center)
          .margin({ bottom: 14 })

        // ═══════════════════════════════════════════
        // Daily Goal — tap to expand inline editor
        // ═══════════════════════════════════════════
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

        // ═══════════════════════════════════════════
        // Drink Sizes — tap to expand S / M / L editors
        // ═══════════════════════════════════════════
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
              // ── Size S ──
              Row() {
                Text('S')
                  .fontSize(14)
                  .fontWeight(FontWeight.Medium)
                  .fontColor(Constants.COLOR_TEXT_SECONDARY)
                  .width(22)

                Button('−')
                  .fontSize(18)
                  .fontWeight(FontWeight.Bold)
                  .width(42)
                  .height(42)
                  .borderRadius(21)
                  .backgroundColor(Constants.COLOR_PROGRESS_BG)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  .onClick(() => { this.adjustSize(0, -Constants.DRINK_SIZE_STEP); })

                Text(`${this.drinkSize1}`)
                  .fontSize(17)
                  .fontWeight(FontWeight.Bold)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  .layoutWeight(1)
                  .textAlign(TextAlign.Center)

                Button('+')
                  .fontSize(18)
                  .fontWeight(FontWeight.Bold)
                  .width(42)
                  .height(42)
                  .borderRadius(21)
                  .backgroundColor(Constants.COLOR_PROGRESS_BG)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  .onClick(() => { this.adjustSize(0, Constants.DRINK_SIZE_STEP); })
              }
              .width('100%')
              .padding({ left: 14, right: 14, top: 6, bottom: 4 })
              .alignItems(VerticalAlign.Center)

              // ── Size M ──
              Row() {
                Text('M')
                  .fontSize(14)
                  .fontWeight(FontWeight.Medium)
                  .fontColor(Constants.COLOR_TEXT_SECONDARY)
                  .width(22)

                Button('−')
                  .fontSize(18)
                  .fontWeight(FontWeight.Bold)
                  .width(42)
                  .height(42)
                  .borderRadius(21)
                  .backgroundColor(Constants.COLOR_PROGRESS_BG)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  .onClick(() => { this.adjustSize(1, -Constants.DRINK_SIZE_STEP); })

                Text(`${this.drinkSize2}`)
                  .fontSize(17)
                  .fontWeight(FontWeight.Bold)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  .layoutWeight(1)
                  .textAlign(TextAlign.Center)

                Button('+')
                  .fontSize(18)
                  .fontWeight(FontWeight.Bold)
                  .width(42)
                  .height(42)
                  .borderRadius(21)
                  .backgroundColor(Constants.COLOR_PROGRESS_BG)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  .onClick(() => { this.adjustSize(1, Constants.DRINK_SIZE_STEP); })
              }
              .width('100%')
              .padding({ left: 14, right: 14, top: 4, bottom: 4 })
              .alignItems(VerticalAlign.Center)

              // ── Size L ──
              Row() {
                Text('L')
                  .fontSize(14)
                  .fontWeight(FontWeight.Medium)
                  .fontColor(Constants.COLOR_TEXT_SECONDARY)
                  .width(22)

                Button('−')
                  .fontSize(18)
                  .fontWeight(FontWeight.Bold)
                  .width(42)
                  .height(42)
                  .borderRadius(21)
                  .backgroundColor(Constants.COLOR_PROGRESS_BG)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  .onClick(() => { this.adjustSize(2, -Constants.DRINK_SIZE_STEP); })

                Text(`${this.drinkSize3}`)
                  .fontSize(17)
                  .fontWeight(FontWeight.Bold)
                  .fontColor(Constants.COLOR_TEXT_PRIMARY)
                  .layoutWeight(1)
                  .textAlign(TextAlign.Center)

                Button('+')
                  .fontSize(18)
                  .fontWeight(FontWeight.Bold)
                  .width(42)
                  .height(42)
                  .borderRadius(21)
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

        // ═══════════════════════════════════════════
        // Reminders — toggle + expandable interval
        // ═══════════════════════════════════════════
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
                .fontSize(20)
                .fontWeight(FontWeight.Bold)
                .width(46)
                .height(46)
                .borderRadius(23)
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
                .fontSize(20)
                .fontWeight(FontWeight.Bold)
                .width(46)
                .height(46)
                .borderRadius(23)
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

        // ═══════════════════════════════════════════
        // HA Sync — toggle + test connection button
        // ═══════════════════════════════════════════
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

        // ═══════════════════════════════════════════
        // Health Server — toggle with status subtitle
        // ═══════════════════════════════════════════
        Row() {
          this.settingIcon('⬡', '#546E7A')

          Column() {
            Text('Health Server')
              .fontSize(15)
              .fontWeight(FontWeight.Medium)
              .fontColor(Constants.COLOR_TEXT_PRIMARY)
            if (this.serverEnabled) {
              Text(this.serverUrl.length > 0 ? '● Connected' : '○ No URL set')
                .fontSize(11)
                .fontColor(
                  this.serverUrl.length > 0
                    ? Constants.COLOR_SUCCESS
                    : Constants.COLOR_TEXT_SECONDARY
                )
                .margin({ top: 2 })
            }
          }
          .layoutWeight(1)
          .alignItems(HorizontalAlign.Start)

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

        // ═══════════════════════════════════════════
        // Manage Entries — navigate to detail page
        // ═══════════════════════════════════════════
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

        // ═══ Back ═══
        Button('← Back')
          .fontSize(14)
          .fontWeight(FontWeight.Medium)
          .height(44)
          .width(120)
          .borderRadius(22)
          .backgroundColor(Constants.COLOR_SURFACE)
          .fontColor(Constants.COLOR_PRIMARY)
          .margin({ top: 4, bottom: 20 })
          .onClick(() => { router.back(); })
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
    .height('100%')
    .scrollBar(BarState.Off)
    .backgroundColor(Constants.COLOR_BACKGROUND)
  }
}
