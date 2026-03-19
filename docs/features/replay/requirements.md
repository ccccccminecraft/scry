# リプレイ機能 要件定義

## 概要

対戦データをターン・フェーズ単位で再生できるリプレイ機能。
参考: [untapped.gg](https://untapped.gg) のリプレイビューア。

---

## 目的

- 自分のプレイを後から振り返り、判断の是非を確認する
- ミスやテンポロスが発生したターンを特定する
- AI 分析との連携（「このゲームのターン5を見て」といった具体的な文脈を提供する）

---

## 機能要件

### FR-01 再生コントロール

- 再生・一時停止・コマ送り（1アクション単位）が可能
- ターン単位のジャンプ（「ターン7へ」）
- フェーズ単位のジャンプ（メイン1・戦闘・メイン2等）
- スライダーで任意の時点に移動

### FR-02 ボード表示

再生中の任意の時点で以下を表示する。

| 表示要素 | 詳細 |
|---------|------|
| バトルフィールド | 各プレイヤーのパーマネント一覧（カード名・タップ状態） |
| 手札 | 枚数（自プレイヤーはカード名も表示） |
| 墓地 | カード一覧 |
| 追放 | カード一覧 |
| ライブラリ | 残枚数 |
| ライフ総量 | 両プレイヤーの現在ライフ |
| 現在フェーズ | どのフェーズ・ステップか |
| スタック | 現在スタックにある呪文・能力 |

### FR-03 イベントログ

再生と連動して、現在時点までのアクションをハイライト表示する。

### FR-04 戦闘の可視化

- 攻撃クリーチャーと対応するブロッカーをペアで表示
- ダメージ割り振りの結果を表示

### FR-05 対応するゲームへのアクセス

- 対戦詳細画面（MatchDetailView）のゲーム一覧から各ゲームのリプレイを開ける

---

## 非機能要件

### NFR-01 対応データソース

| ソース | 優先度 | 備考 |
|--------|--------|------|
| MTGA（Surveil JSON） | 高 | イベントが詳細で取得可能な情報が多い |
| MTGO（.dat） | 中 | ログの情報量に制約あり（後述） |

### NFR-02 再生速度

- 操作に対して 100ms 以内に描画が更新されること

### NFR-03 ストレージ

- リプレイデータの追加により、1試合あたりの DB サイズが現在の 10 倍以内に収まること

---

## データソース別の制約と実現可能性

> サンプルデータ（`docs/sample_data/surveil/`・`docs/sample_data/mtga_log/Player.log`）による調査結果を反映。

### MTGA データソースの構造

MTGAには2種類のデータソースがある。

| ソース | 形式 | 特徴 |
|--------|------|------|
| **Player.log** | JSON Lines（GRE メッセージ） | 完全なゲーム状態スナップショット（GameStateMessage）を含む |
| **Surveil JSON** | schema_version=2 イベントログ | Player.log を解析・変換した17種類のイベント列 |

### MTGA（Surveil JSON）

17種類のイベントタイプを含む。

| 情報 | 取得可否 | 備考 |
|------|---------|------|
| ライフ変化 | ✅ | `life_change` イベント（delta + total） |
| フェーズ・ステップ | ✅ | `phase_change` イベント |
| 戦闘ペアリング | ✅ | `block` イベントに `blocking[]` 配列あり |
| ダメージ | ✅ | `damage` イベント（source / target / amount） |
| ドロー・ディスカード | ✅ | `draw` / `discard` イベント |
| パーマネントID（個別追跡） | ❌ | `grp_id`（カード種別ID）のみ。同名カード2枚の区別不可 |
| ゾーン変更（場への着地・死亡等） | ❌ | cast/resolve はあるが ETB・死亡は記録なし |
| タップ状態 | ❌ | マナ能力起動から推測のみ。明示的な記録なし |
| 初期手札の内容 | ❌ | mulligan イベントのみ。ゲーム開始時の手札不明 |
| スタック上の順序 | ❌ | cast→resolve の対応はあるが応答の積み重ねなし |
| ダメージ割り当て詳細 | ❌ | 複数ブロッカーへの割り当て情報なし |

**結論: Surveil JSON ベースでは部分的なリプレイのみ実現可能。**

### MTGA（Player.log）

`GREMessageType_GameStateMessage` に完全なゲーム状態が記録されている。

| 情報 | 取得可否 | 備考 |
|------|---------|------|
| 個別カードID（instanceId） | ✅ | 全ゲームオブジェクトに一意 ID |
| 全ゾーンの内容 | ✅ | Hand / Library / Battlefield / Graveyard / Exile / Stack / Sideboard |
| タップ状態 | ✅ | `isTapped: true/false` |
| カード特性 | ✅ | power / toughness / cardTypes / color |
| ライフ総量 | ✅ | `players[].lifeTotal` |
| フェーズ・ステップ | ✅ | `turnInfo.phase` / `turnInfo.step`（詳細ステップまで） |
| スタック状態 | ✅ | `zones[ZoneType_Stack]` |
| 攻撃・ブロック | ✅ | `attackState` / `blockingGroup` |
| ダメージ割り当て | ✅ | `AssignDamageReq` メッセージ |
| 初期手札 | ✅ | GameStateType_Full で初期状態を保持 |
| 相手の手札内容 | ❌ | `Visibility_Private` のため秘匿 |
| カードの盤面座標 | ❌ | 位置データなし |

**結論: Player.log ベースでほぼ完全なリプレイが実現可能。**

### MTGO（.dat ログ）

「実況テキスト」形式のため、**状態の完全な再現には情報が不足**する。現在捨てているパーマネントIDを保存することで追跡精度は向上するが、以下は取得困難。

| 情報 | 取得可否 |
|------|---------|
| パーマネントID | ✅ ログにあり（現在未保存） |
| ゾーン変更 | △ 一部のみ（メッセージパターン次第） |
| ライフ変化 | ❌ ログに記録なし |
| タップ状態 | ❌ ログに記録なし |
| 戦闘ペアリング（詳細） | △ 攻撃者は取得可、ブロック対応は不完全 |
| 手札内容 | △ ドロー・ディスカードから推定可能（完全ではない） |

---

## 現在のデータモデルに不足している点

### 1. パーマネントIDの未保存

MTGO ログの `@[CardName@:multiverseId,**permanentId**:@]` に含まれる permanentId を現在は破棄している。同名カードの複数枚追跡に必須。

→ `actions.permanent_id` カラムの追加が必要。

### 2. ゾーン変更イベントの欠落

「唱えた」は記録しているが、その後の「場に出た」「死亡した」「追放された」「手札に戻った」が記録されていない。

→ `zone_changes` テーブルの追加が必要。

### 3. ライフ変化の未記録

→ `life_events` テーブルの追加が必要（MTGA のみ取得可能）。

### 4. 戦闘ペアリングの欠落

どの攻撃クリーチャーをどのクリーチャーがブロックしたかのペアが記録されていない。

→ `combat_pairings` テーブルの追加が必要。

### 5. フェーズ粒度の不足

`actions.phase` は MTGA のみ記録。MTGO はフェーズ情報がなく、ターン単位の再生にとどまる。

### 6. ゲーム開始時の手札未記録

マリガン後の初期手札が記録されていない（ドローからの推定は不完全）。

---

## 必要な新規テーブル（概要）

詳細は詳細設計ドキュメント（design.md）で定義する。

```
permanent_instances   個別パーマネントの追跡
  game_id / permanent_id / card_name / controller / owner

zone_changes          ゾーン遷移イベント
  game_id / sequence / permanent_id / from_zone / to_zone / cause_action_id

life_events           ライフ変化（MTGA のみ）
  game_id / sequence / player_name / life_total

combat_pairings       攻撃・ブロックのペアリング
  game_id / turn / attacker_permanent_id / blocker_permanent_id
```

ゾーン値: `hand` / `battlefield` / `graveyard` / `exile` / `library` / `stack`

---

## 段階的実装方針

一度に全機能を実装するのではなく、以下の順で段階的に進める。

| フェーズ | 内容 |
|---------|------|
| Phase 1 | データ基盤整備：permanentId 保存・zone_changes・life_events を追加し、インポート時に記録する |
| Phase 2 | MTGA リプレイ：Surveil データを使ったイベントログ再生 UI（ボード表示なし・テキストログ形式） |
| Phase 3 | ボード可視化：バトルフィールド・手札・墓地をカード画像で表示 |
| Phase 4 | MTGO 対応：取得可能な情報の範囲でリプレイ再現 |

---

## 未解決事項

- [x] Surveil JSON で取得できる全イベントタイプの確認 → 17種類を確認。タップ状態・ゾーン変更・初期手札が欠落していることが判明
- [x] Player.log との差分分析 → Player.log ベースであればほぼ完全なリプレイが実現可能であることを確認
- [ ] **MTGO ログでゾーン変更メッセージがどの程度存在するか調査**（次の調査対象）
- [ ] リプレイ UI のフレームワーク選定（Canvas / SVG / CSS レイアウト）
- [ ] 既存の取り込み済みデータへの遡及適用方針（新規インポート分のみ対応とするか）
- [ ] ストレージ増大の許容範囲確認

## 調査ログ

### 2026-03-19 Surveil JSON / Player.log 調査

**調査対象**
- `docs/sample_data/surveil/*.json`（Surveil JSON 出力）
- `docs/sample_data/mtga_log/Player.log`（MTGA 生ログ）

**主要な発見**

1. **Surveil JSON の限界**: `grp_id`（カード種別ID）しか持たず、個別パーマネントの追跡が不可能。タップ状態・ゾーン変更・初期手札も欠落。
2. **Player.log の可能性**: `GREMessageType_GameStateMessage` に完全なゲーム状態が記録されており、`instanceId` による個別カード追跡・全ゾーン内容・タップ状態・フェーズ詳細が取得可能。
3. **実装パスの結論**: Surveil を拡張するより Player.log を直接パースするほうがリプレイに必要な情報を完全に取得できる。Surveil はインポート用として継続使用し、リプレイ用には Player.log パーサーを新規実装する方向が現実的。

**Surveil 拡張で対応可能な項目（短期）**
- `instance_id` フィールドの追加（各カードの一意ID）
- `tapped` / `untapped` イベントの追加
- `zone_change` イベントの追加（ETB・死亡・追放等）
- `initial_hand` イベントの追加（ゲーム開始時手札）
- `damage_allocation` 詳細フィールドの追加
