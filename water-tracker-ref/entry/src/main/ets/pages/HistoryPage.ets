/**
 * HistoryPage — 7-day water intake history with horizontal bar chart.
 *
 * Uses tile navigation (vertical layout on one page) per wearable guidelines.
 * Layout respects round watch spacing: 26 vp left/right margins.
 *
 * @see https://developer.huawei.com/consumer/en/doc/design-guides/application-architecture-0000002202799801
 */
import router from '@ohos.router';
import { Constants } from '../common/Constants';
import { StorageService } from '../service/StorageService';
import { DayLog, WaterModel } from '../model/WaterModel';

@Entry
@Component
struct HistoryPage {
  @State private weekHistory: DayLog[] = [];
  @State private dailyGoal: number = Constants.DEFAULT_DAILY_GOAL;
  @State private isLoading: boolean = true;

  aboutToAppear(): void {
    this.loadHistory();
  }

  private async loadHistory(): Promise<void> {
    this.dailyGoal = await StorageService.getDailyGoal();
    this.weekHistory = await StorageService.getWeekHistory();
    this.isLoading = false;
  }

  private getDayLabel(dateStr: string): string {
    const todayStr: string = WaterModel.getTodayDateString();
    if (dateStr === todayStr) {
      return 'Today';
    }
    const today = new Date();
    const yesterday = new Date(today.getTime());
    yesterday.setDate(yesterday.getDate() - 1);
    const yMonth: string = String(yesterday.getMonth() + 1).padStart(2, '0');
    const yDay: string = String(yesterday.getDate()).padStart(2, '0');
    const yStr: string = `${yesterday.getFullYear()}-${yMonth}-${yDay}`;
    if (dateStr === yStr) {
      return 'Yday';
    }
    const days: string[] = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const d = new Date(dateStr + 'T00:00:00');
    return days[d.getDay()];
  }

  private getBarPercent(intake: number): number {
    return Math.min(Math.max((intake / this.dailyGoal) * 100, 0), 100);
  }

  build() {
    Column() {
      // ── Title ──
      Text('History')
        .fontSize(14)
        .fontWeight(FontWeight.Bold)
        .fontColor(Constants.COLOR_TEXT_PRIMARY)
        .textAlign(TextAlign.Center)

      if (this.isLoading) {
        Text('Loading...')
          .fontSize(12)
          .fontColor(Constants.COLOR_TEXT_SECONDARY)
          .margin({ top: 20 })
      } else {
        // ── Bar chart ──
        Column() {
          ForEach(this.weekHistory, (log: DayLog) => {
            Row() {
              Text(this.getDayLabel(log.date))
                .fontSize(9)
                .fontColor(Constants.COLOR_TEXT_SECONDARY)
                .width(30)
                .textAlign(TextAlign.End)
                .margin({ right: 4 })

              Stack({ alignContent: Alignment.Start }) {
                Row()
                  .width('100%')
                  .height(10)
                  .borderRadius(5)
                  .backgroundColor(Constants.COLOR_PROGRESS_BG)

                Row()
                  .width(`${this.getBarPercent(log.totalIntake)}%`)
                  .height(10)
                  .borderRadius(5)
                  .backgroundColor(
                    log.totalIntake >= this.dailyGoal
                      ? Constants.COLOR_SUCCESS
                      : Constants.COLOR_PRIMARY
                  )
              }
              .layoutWeight(1)
              .height(10)

              Text(`${log.totalIntake}`)
                .fontSize(8)
                .fontColor(Constants.COLOR_TEXT_SECONDARY)
                .width(28)
                .textAlign(TextAlign.End)
                .margin({ left: 3 })
            }
            .width('100%')
            .height(20)
          }, (log: DayLog) => log.date)
        }
        .width(180)
        .margin({ top: 6 })
      }

      // ── Back ──
      Text('← Back')
        .fontSize(11)
        .fontColor(Constants.COLOR_PRIMARY)
        .margin({ top: 8 })
        .onClick(() => { router.back(); })
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
    .padding({ left: Constants.MARGIN_LEFT, right: Constants.MARGIN_RIGHT })
    .backgroundColor(Constants.COLOR_BACKGROUND)
  }
}
