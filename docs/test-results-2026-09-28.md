# テスト結果（2026-09-28）

- テスト要綱：[docs/test-plan.md](test-plan.md)
- 環境：Windows 11、Python 3.14.7、PyInstaller 6.22.3、同じ Windows ユーザーの DPAPI。
- 対象：現行ソース、`release\TeamsAutoJoin`、`dist\TeamsAutoJoin`。

## 実施結果

| ID | 判定 | 実測・証跡 |
|---|---|---|
| AT-01 | 合格 | 単体・受入観点の自動テスト13件、失敗0件。`python -m unittest discover -s tests -v`。既存5件に予約検証、人数境界、履歴保存期間、通知、遅延予約など8件を追加。 |
| AT-02 | 合格 | `python main.py --self-test` の終了コード0、診断 `OK`。`.smoke/source-acceptance.txt`。 |
| AT-03 | 合格 | 両配布先で必須ファイルを確認。`base_library.zip` の破損なし、`encodings/__init__.pyc` を確認。 |
| AT-04 | 合格 | `release` と `dist` の各 EXE で終了コード0、診断 `OK`。`.smoke/release-acceptance.txt`、`.smoke/dist-acceptance.txt`。 |
| AT-05 | 合格 | `release` フォルダー一式を別パスへコピーして終了コード0、診断 `OK`。`.smoke/relocated-acceptance.txt`。 |
| AT-06 | 一部確認 | 隔離データ領域で通常起動し、プロセス継続とウィンドウタイトル「Teams 自動入退室」を確認。Windows UI Automation ではこの Tkinter 画面のラベル文字列を取得できず、初期状態と操作は目視未確認。 |
| MT-01〜MT-16 | 未実施 | Teams プロセスの起動は確認したが、専用テスト会議・主催者・人数変更用の協力者を使った操作は未実施。 |

単体テストを最初にサンドボックス内で実行した際、DPAPI の保存ケースが OS エラーで失敗した。通常の Windows ユーザー環境で同じテストを再実行し、13件すべて成功した。これは環境差の切り分け結果であり、実機での保存・再起動確認（MT-12）は引き続き必要。

## 受入判定

自動テストと配布 EXE の自己診断は合格。GUI の画面内操作と Teams 実連携は未確認のため、AC-01〜AC-22 の受入完了判定は保留。特に3方式の参加、マイク・カメラ、チャット送信、人数取得と退出、ロビー、表示条件は MT-03〜MT-15 で確認する。
