# Next Chat Start Here

Paste this into a new chat:

@GitHub
@Railway

新競艇AI開発プロジェクトNo.2の続きです。

最初に `kenshoushouri-cloud/boat-ai-v2` の次の3点だけを読んでください。
1. `docs/HANDOFF_LATEST.md`
2. そこが指定する current compact handoff を全文
3. `docs/NEXT_CHAT_START_HERE.md`

古いhandoffは履歴扱いです。
SHA・run・件数・容量は固定値にせず、次の1作業に必要なものだけlive再取得してください。

重要:
- 1回に1作業
- 出力は短く
- `list_variables` 禁止
- 購入・プラン変更・容量変更禁止
- TOTO staged patchに触れない
- Issue #42の全コメント取得は禁止。巨大なので、最新run/job logsを優先し、必要ならコメント末尾だけ取得する
- **Railway運用コストは、不足データ取得・バックフィル再開後も月額USD 20以下が最低条件。安いほど良い。**
- **Production・バックテスト・実テスト・学習・データ取得・復元保護・システム構築に必要な機能やデータは、コスト削減目的だけでは削らない。**
- **Railway Agent / Railway AIは使用禁止。Agent token課金が請求に影響するため、直接のread-only status / metrics / logs / docsを使う。**
- 新しい常時稼働service / DB / Replica / Volumeなど継続課金を増やす変更は原則しない。必要な場合は、月額影響と安価な代替案を先に示し、明示承認を得る。
- 不足データ取得は、既存リソースを使う短時間実行を優先し、無駄な二重実行・再実行を避ける。

確認後、current compact handoffの「Next single task」から続けてください。
