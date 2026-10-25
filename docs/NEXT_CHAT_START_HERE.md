# 新チャット起点（2026-10-26、V5優先）

@GitHub
@Railway

Repository `kenshoushouri-cloud/boat-ai-v2`。最初に `docs/HANDOFF_LATEST.md` → 指定compact → 本ファイルのみ参照。過去の長文ログは必要箇所だけ。

ConoHaの旧 `public.v2_*` にcollectorが書込中、13 `boat_data` VIEWは旧原本参照、V5 stage13物理表の初回+表別差分追込済み（10/26 03:16の時点、CDCなし）。正式writer cutover0/13、BUY OFF。V5 LIVE VIEW読み取り専用5分shadow monitorが起動したが、実V5予測計算はまだ未稼働。旧collectorは停止不可、odds/展示/気象の再現不可能な時点観測を保護。独立バックアップ復元gateも未完。

10/26朝 collectorは07:34時点200/288実行中、failed=0、丸亀8艇で選手成績解析の13値一括NULL疑い。13項目全部必須は不採用、**正当な未集計は高評価選手を減点せず**、解析失敗と出所不明はHOLD。pure policy `v5/entry_quality_policy.py` と synthetic tests追加済み（実行未検証）。稼働中コードには未反映。`docs/V5_ENTRY_MISSINGNESS_POLICY_20261026.md`参照。

**Next ONE task:** 朝収集288/288終了をTermius READ ONLY確認→丸亀1RのHTML解析で未集計かパーサ失敗か区別。自動買いOFF、新しいcore policyのテスト実行後にV5実データadapterへ統合、今はcollectorの書換え・複製GET・原本削除・V5物理writer切替禁止。
