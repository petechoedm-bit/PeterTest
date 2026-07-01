# ✈️ Flight Price Compare

一個可自訂搜尋、即時比價、並能定時監控 + 降價通知的機票比價工具。

- **可自訂搜尋** — 出發地、目的地、日期、人數、幣別、是否直飛全部自訂
- **多來源比價** — 抽象化的 provider 介面，一次查詢所有來源，由便宜到貴排序
- **即時查詢** — `search` 指令或 `web` 網頁介面，馬上查、馬上比
- **定時監控** — `monitor` 指令，依設定的間隔自動查價，低於目標價就通知
- **價格歷史** — SQLite 記錄每次查價，顯示與上次比較的漲跌趨勢
- **免申請即可試用** — 沒有 API key 時自動用 Demo 模式產生擬真資料，整套流程都能跑

## 安裝

```bash
pip install -r requirements.txt
```

## 即時比價

```bash
# 台北 → 東京 來回，2 位大人
python -m flightprice search TPE NRT 2026-07-20 2026-07-27 --adults 2 --currency TWD

# 單程、只看直飛、顯示前 5 筆
python -m flightprice search TPE KIX 2026-08-15 --non-stop --top 5
```

範例輸出：

```
Searching via: demo

TPE → NRT  2026-07-20 / 2026-07-27  (round-trip, 2 pax)

⭐  1. 15840 TWD  [Jetstar Japan]  TPE → NRT → TPE
    2. 16720 TWD  [Tigerair Taiwan]  TPE → NRT → TPE
    ...
Cheapest: 15840 TWD via demo (Jetstar Japan)
```

## 網頁介面

不想打指令的話，用瀏覽器查：

```bash
python -m flightprice web
```

開啟 <http://127.0.0.1:5000/>，填表單送出即可看到比價結果（只在本機開放，不對外）。

出發地/目的地欄位支援輸入城市中文名稱（常用城市，如「台北」「東京」）、英文名稱或 IATA 代碼自動完成，
這部分是純離線比對（`flightprice/data/airports.json` + `city_aliases_zh.json`），不會呼叫 Skyscanner API，
不消耗免費額度。

## 定時監控 + 降價通知

1. 複製設定檔並填入你要盯的航線與目標價：

   ```bash
   cp watches.example.yaml watches.yaml
   ```

2. 執行監控（`--once` 先跑一次看看，不加就會依 `check_interval_minutes` 持續執行）：

   ```bash
   python -m flightprice monitor --config watches.yaml --once
   python -m flightprice monitor --config watches.yaml
   ```

當最低價 ≤ `max_price` 時會發出通知。設定了 SMTP 就寄 email，否則印在終端機。

## 使用真實資料

Demo 模式免申請即可用。想接真實航班資料，複製 `.env.example` 為 `.env` 後填入以下任一（或兩者都填，會同時查詢比價）：

**Skyscanner**（推薦，Amadeus Self-Service 已於 2026-07-17 關閉）

到 <https://rapidapi.com/apiheya/api/sky-scrapper> 訂閱 BASIC 免費方案（不需信用卡，20 次/月），取得 RapidAPI Key 後填入：

```bash
SKYSCANNER_RAPIDAPI_KEY=你的_key
```

**Amadeus**（已停用，僅供既有憑證參考）

```bash
AMADEUS_CLIENT_ID=
AMADEUS_CLIENT_SECRET=
```

偵測到任一憑證後會自動啟用對應來源，都沒填就維持 Demo 模式。

## 專案結構

```
flightprice/
  models.py            # SearchQuery / FlightOffer / 價格觀測 等資料模型
  compare.py           # 跨 provider 彙整、排序
  storage.py           # SQLite 價格歷史
  notify.py            # Email / console 通知
  config.py            # .env 與 watches.yaml 載入
  monitor.py           # 排程監控 + 門檻警示
  cli.py               # search / monitor / web 指令
  webapp.py            # 本機網頁介面（Flask）
  templates/           # 網頁介面的 HTML
  providers/
    base.py            # FlightProvider 抽象介面
    amadeus.py         # Amadeus 真實資料（已停用）
    skyscanner.py       # Skyscanner 真實資料（Sky Scrapper RapidAPI）
    demo.py            # 離線擬真資料
tests/
  test_flightprice.py
```

## 新增資料來源

繼承 `FlightProvider`、實作 `search()`，再加進 `providers/__init__.py` 的
`build_providers()` 即可（例如 Kiwi）。

## 測試

```bash
python -m unittest discover -s tests -v
```
