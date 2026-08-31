# boat-ai-v2 — ChatGPT Project Migration Redirect

更新日時: 2026-08-31 JST

このファイルは旧「競艇AI開発プロジェクト No.1〜No.6」からの移行入口。
**新しいChatGPTチャットでは、ここから巨大な履歴を読み込まない。**

## Active startup

最初に読むファイルは次の1つだけ:

- **`docs/CHATGPT_BOOTSTRAP.md`**

その後、現在のタスクに応じて:
- Railway / DB / pipeline → `docs/OPS_STATE.md`
- prediction / Shadow / Forward → `docs/RESEARCH_STATE.md`

## Do not load at startup

開始時に以下を全文取得しない:
- `docs/PROJECT_HANDOFF.md`
- `docs/PROJECT_HISTORY.md`
- `docs/DEVELOPMENT_STATUS.md`
- GitHub Issue #42 comments
- 過去チャット No.1〜No.6

必要な情報だけ、機能名・PR番号・日付・エラー名で部分検索する。

## Archive

このファイルの旧詳細版は:
- `docs/archive/CHATGPT_PROJECT_MIGRATION_LEGACY_20260831.md`

詳細な開発経緯は:
- `docs/PROJECT_HANDOFF.md`
- `docs/PROJECT_HISTORY.md`
- Git history / relevant PR

Archiveは通常の新規チャット開始時には読まない。

## New-project first message

> GitHub `kenshoushouri-cloud/boat-ai-v2` の `docs/CHATGPT_BOOTSTRAP.md` だけを最初に読んで現在地点を確認してください。過去チャット No.1〜No.6、PROJECT_HANDOFF、PROJECT_HISTORY、DEVELOPMENT_STATUS、Issue #42のコメント全件は開始時に取得しないでください。current mainとopen PRだけ短く再確認し、今回の作業がOpsならOPS_STATE、研究ならRESEARCH_STATEだけ追加で読んでください。過去判断が必要になった場合だけ対象箇所を部分検索してください。

## Principle

**GitHub = persistent state**
**ChatGPT chat = temporary workspace**

チャット番号を連鎖させて記憶を運ばない。
作業後にstateが変わった時だけBOOTSTRAP / OPS_STATE / RESEARCH_STATEを上書き更新する。
