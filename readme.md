# Teams 自動入退室アプリの使い方

## 起動

Windows 11で `release\TeamsAutoJoin\TeamsAutoJoin.exe` を起動します。配布するときは `release\TeamsAutoJoin` フォルダーをまとめてコピーしてください。初回起動時は自動運転が一時停止しています。

ソースから起動する場合はPython 3.14を用意し、作業フォルダーで次を実行します。

```powershell
python -m pip install --target .deps -r requirements.txt
python main.py
```

EXEの再作成は `powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1` で行います。

## 予約

1. 月表示カレンダーで日を選び、［追加］を押します。
2. 会議名、開始・終了予定日時を `YYYY-MM-DD HH:MM` で入力します。時刻は日本時間です。
3. 参加方式を選びます。
   - 「会議IDとパスワード」：会議IDとパスワードを入力します。
   - 「会議リンク」：Teamsの `https://teams.microsoft.com/l/meetup-join/...` リンクを入力します。
   - 「Teamsの参加ボタン」：Teamsの予定表にも同じ会議名・開始日時の予定が必要です。
4. 毎週の予定なら［毎週繰り返す］にチェックし、終了日を入力します。
5. ［保存］を押します。前の予定の終了から次の予定の開始までは10分以上必要です。
6. ［自動運転開始］を押します。予約があっても一時停止中は参加しません。

実行中の会議予約は編集・削除できません。毎週の予約は、選択した回だけかシリーズ全体かを選べます。

## 動作と保存先

- マイクとカメラをオフにできない場合や、予定を一意に見つけられない場合は参加しません。
- 会議チャットへの挨拶、参加者数の監視、人数条件での退出を行います。
- 会議の終了予定10分前と5分前に音で知らせます。次の会議5分前にも今の会議が続いていれば知らせます。
- 予約は同じWindowsユーザーの `%LOCALAPPDATA%\TeamsAutoJoin\meetings.json` に保存します。パスワードと参加リンクはWindowsのユーザー保護機能で暗号化します。
- 実行履歴は `%LOCALAPPDATA%\TeamsAutoJoin\history.json` に最大30日保存します。パスワード、参加リンク、会議チャット本文は記録しません。
- 一時停止中も通知は続きます。ロック・スリープ・切断後は自動運転が停止します。

## Teamsでの実機確認

Teamsの画面要素名はバージョンや所属組織の設定で変わり得ます。最初は影響のないテスト会議で、参加方式ごとに入室画面、マイク・カメラ、チャット、人数、退出を確認してください。対象を一意に判別できないときは操作を中止し、アプリ内に履歴を残します。UI Automationの識別子を実機で確認してから通常運用に移してください。

参加リンクは、Microsoftが案内する `msteams://` プロトコルを使ってデスクトップアプリへ渡します。Teamsの会議ID参加と予定表からの参加手順も、Microsoftの案内に基づいています。

- [Microsoft Teamsの会議参加方法](https://support.microsoft.com/en-us/teams/meetings/join-a-meeting-in-microsoft-teams)
- [Teamsディープリンクのプロトコル](https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/build-and-test/deep-links)
