# V5締切前証拠フリーズ入口 — 限定静的監査（2026-10-14 JST）

**判定：現行V5主力の直前情報（beforeinfo）取得・保存はHARD HOLD。本番凍結/Forward/BUYを許可できない。** 既存ConoHa VPSの管理画面/SSHは未確認、10/14時点でサポート返信未着。作業はGitHub feature内のコード読取のみ（ネットワーク実行、DB接続、テスト起動、CI、Railway/ConoHa変更なし）。

参照のGit blob（この監査時点）：`v5/official_capture_pipeline.py`=`0831dcfc768ef2598f97f1615b94bed3b3eec2a8`、`v5/official_http_transport.py`=`734535c1a31cc436ae2882660f52de490ae99095`、`v5/official_http_receipt.py`=`351d4151d93c8c342ddf8f2b2122e029cb7e2da4`、`v5/official_first_write_storage.py`=`d32bc29b4a5710f347b3b03ed498db54504f94be`、`v5/official_first_write_executor.py`=`a9ba63e4436d2fea8c56a201bae8ca3405362615`、`v5/beforeinfo_prewrite_gate.py`=`e0620647499c90ee915b4fa7bd4488513c3af13c`、`v5/official_racelist_readback.py`=`3d05d70e7e520537bc6c4b42f9566da992bef8e1`、`v5/official_start_status_provenance.py`=`fe8884fb1e43df05e5fe4e702934bc51ab7e49d0`。

## 確認結果

1. **直前情報のpre-HTTP停止が入口に存在。** `official_capture_pipeline.py:57-72`は`storage_enabled is True`の明示指定を要求し、`expected_source=="official_beforeinfo"`は`BEFOREINFO_PRE_HTTP_HARD_HOLD_NO_AUTHENTICATED_POSITIVE_START`で**session.GET/DB SELECT/DB書込の前に例外停止**する。後続の直前情報チェックブロック（同:89-133）は現状到達不能。これを外しても無条件で本番準備完了にはならない。
2. **締切前かつ6艇の出走状態が確実という肯定証拠が未解決。** `beforeinfo_prewrite_gate.py:71-83`は`request_started_at <= response_completed_at < prediction_cutoff_at <= official_deadline_at`等を要求。`beforeinfo_prewrite_gate.py:179-182`は独立して`ACTIVE_START_STATUS_NOT_PROVEN`を返す。`official_start_status_provenance.py`は出走6艇の明示的肯定情報を証明できず`all_six_active_confirmed=False`/`forward_eligible=False`。`official_racelist_readback.py`も**原本6艇の候補抽出は出走確定の証明ではない**とする。
3. **元HTML/HTTP収集時刻を「最初の取得」へ昇格しない。** `official_http_transport.py`は1回のバイト列と応答完了時刻の提案作成のみでDB書込をしない。`official_http_receipt.py`は公式URL・応答コード・redirect・時刻を検証するが、公式公開時刻・独立した初回観測を証明しない。
4. **初回のDB格納は整合性検査に限定。** `official_first_write_storage.py`は`ON CONFLICT DO NOTHING`と同一resource原本読出し。`official_first_write_executor.py`は1取引でINSERT/SELECT・バイト/ハッシュ照合、異常時rollback。DBの`stored_at`を取得時刻や締切前証拠とみなさない。正常保存も`first_observed_at=None`、`first_write_confirmed=False`、`forward_eligible=False`のまま。
5. **限定的な追加注意：** `capture_and_store_v5_official_source`の`official_deadline_at`・`prediction_cutoff_at`による事前判定は**beforeinfo分岐専用**。racelist/Kの提案格納経路については入口レベルでレース締切前保証が成立しない。期限後の格納自体を締切前証拠に転用してはならない。入口は「NOT deployed」「isolated V5 INSERT+SELECT-only account needed」と明記、実運用Cron/権限/正しい接続先は未検証。

## 保護条件と次の優先度

- **BUY HARD HOLD**、Forward未解禁、67週OOS 0/67、実ROI未検証。履歴・日時だけの後付けを締切前証拠として採用しない。PENDING/UNKNOWN/NO_BUYを削らない。
- 本ターンの監査は**ソース読取だけ**。テストPASS・実通信・実DB凍結を新たに確認したものではない。既存V4本番と4DB原本、CMS鍵、main、cron、料金は無変更。
## 2026-10-14：入口安全ゲートの隔離オフライン動作検証

- `v5/test_capture_entry_forward_hold_offline.py`をfeatureへ追加。**16件のPython unittest定義**：beforeinfo事前HOLD（HTTP/DBを呼ばない）、偽の6艇確認入力、依存欠落、opt-in要件、racelist/K保存後の`forward_eligible=False`、偽の`first_observed_at`/first-write確定フラグを拒否。
- 監査済み実入口`v5/official_capture_pipeline.py`のGit blob `0831dcfc768ef2598f97f1615b94bed3b3eec2a8`をテスト内で固定。ASTから該当関数のみ抽出、fake HTTPとfake DBで注入する設計。**ユーザー環境への通信/DB/有料CIは行わない**。
- **実行結果：Python 3.13 / `python3 -I` 隔離ローカル環境で16/16 PASS。** GitHub原本とテストのblob一致を確認してから実行。初回9/16 PASS・7/16失敗は**モックの例外3種類を全て`Rejected`に別名登録したテスト側の誤り**で、修正後16/16 PASS。修正テストGit blob=`6d42ccdb921523d351a28112929bd5e5d975743d`、入口元blob=`0831dcfc768ef2598f97f1615b94bed3b3eec2a8`。修正版はfeatureに保存しblob一致確認済。ASTで入口関数のみ実行し、HTTP/DBはstubなので**実HTTP・SQL・DB・Forward評価のE2E確認ではない**。ConoHaサポート返信・VPS実機は未確認。

**Next ONE task：** ConoHaの返信/既存2GB管理画面を先に確認。未復旧なら**V5入口の早期HOLD/DB非接続テストと本体の`first-write`契約の間で、実公式時刻とForward判定を誤って承認し得る未検証経路がないか、1件の静的照合**を行う。V4/4DB/ConoHa/実HTTP/実DB/BUY禁止。
