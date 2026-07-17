# AutoBild 爬蟲系統 - 使用手冊

## 快速開始

### 1. 初次設定
雙擊執行 `setup.bat`，它會自動：
- 檢查 Python 環境
- 安裝所有依賴套件
- 安裝 Playwright 瀏覽器
- 產生 PDF 報告

### 2. 執行爬蟲

#### 正常執行
```bash
python run.py
```

#### 測試模式
```bash
python run.py --test
```
測試模式只會處理 2 個品牌、每個品牌 2 個車系、每個車系 3 個款式。

#### 查看進度
```bash
python run.py --status
```

#### 重新開始
```bash
python run.py --reset
```
這會清除所有進度，從頭開始。

## 系統流程

### 啟動流程
1. 載入 `scrape_progress.json` 進度檔案
2. 檢查距上次全面掃描是否超過 7 天
3. 根據檢查結果決定執行模式：
   - **全面掃描模式**：重新掃描所有資料
   - **繼續模式**：從上次中斷處繼續
4. 建立/檢查 SQLite 資料表
5. 初始化批次資料緩衝

### 執行流程
1. 遍歷所有品牌
2. 檢查是否應跳過（已完成的品牌）
3. 儲存品牌進度
4. 遍歷品牌下的所有車系
5. 檢查是否應跳過（已完成的車系）
6. 遍歷車系下的所有款式
7. 隨機延遲 0.65~1.35 秒
8. 取得車輛資料
9. 解析並儲存到批次緩衝
10. 每 100 筆資料批量寫入資料庫
11. 完成一個品牌後匯出 CSV

### 中斷恢復
- 使用者可隨時按 `Ctrl+C` 中斷
- 中斷時自動儲存：
  - 批次資料緩衝
  - 進度檔案
- 重新執行時自動從上次中斷處繼續

## 檔案說明

### 核心模組
- **scraper_config.py**：所有配置設定
- **progress_manager.py**：進度管理，處理斷點續傳
- **database_manager.py**：資料庫管理，處理去重與批次寫入
- **main_scraper.py**：主爬蟲邏輯

### 執行檔
- **run.py**：命令列執行入口
- **setup.bat**：初次設定腳本
- **generate_report.bat**：產生報告腳本

### 資料檔案
- **autobild_master.db**：SQLite 資料庫
- **scrape_progress.json**：進度檔案
- **Brand_Exports/**：CSV 匯出目錄

### 報告檔案
- **AutoBild_爬蟲問題與解決方案.pdf**：完整報告
- **flowchart.png**：系統流程圖

## 進度檔案格式

```json
{
  "last_full_scan": "2026-07-15T10:30:00",
  "current_brand": "BMW",
  "current_model": "3er",
  "completed_brands": ["AUDI", "MERCEDES"],
  "completed_models": {
    "AUDI": ["A3", "A4", "A6"],
    "MERCEDES": ["C-Klasse", "E-Klasse"]
  },
  "stats": {
    "total_records": 1234,
    "brands_processed": 15,
    "models_processed": 89
  }
}
```

## 資料庫查詢範例

### 查看所有品牌統計
```sql
SELECT 廠牌, COUNT(DISTINCT 車型) as 車系數, COUNT(*) as 紀錄數
FROM car_catalog
GROUP BY 廠牌
ORDER BY 紀錄數 DESC;
```

### 查看特定品牌的車系
```sql
SELECT DISTINCT 車型
FROM car_catalog
WHERE 廠牌 = 'BMW'
ORDER BY 車型;
```

### 查看重複資料
```sql
SELECT 廠牌, 車型, 型號, 年份, HSN, TSN, COUNT(*) as 重複次數
FROM car_catalog
GROUP BY 廠牌, 車型, 型號, 年份, HSN, TSN
HAVING COUNT(*) > 1;
```

### 匯出特定品牌資料
```sql
SELECT * FROM car_catalog
WHERE 廠牌 = 'AUDI'
ORDER BY 車型, 型號, 年份;
```

## 常見問題

### Q: 為什麼有些品牌被跳過了？
A: 如果品牌出現在 `completed_brands` 列表中，表示上次已處理完成。使用 `--reset` 可清除進度。

### Q: 如何重新掃描特定品牌？
A: 目前不支援，需使用 `--reset` 清除進度後重新執行。

### Q: CSV 檔案在哪裡？
A: 在 `Brand_Exports` 目錄下，以品牌名稱命名（如 `AUDI.csv`）。

### Q: 資料庫檔案在哪裡？
A: 在目前目錄下的 `autobild_master.db`。

### Q: 如何查看目前進度？
A: 執行 `python run.py --status`。

### Q: 程式中斷後如何恢復？
A: 直接重新執行 `python run.py`，會自動從上次中斷處繼續。

## 技術細節

### 去重機制
- 使用 SQLite 的 UNIQUE 索引
- 插入前檢查資料是否已存在
- 相同的「品牌、車型、型號、年份、HSN、TSN」不會重複記錄

### 批次儲存
- 使用 `batch_data` 列表作為緩衝
- 每 100 筆資料批量寫入資料庫
- 減少 I/O 次數，提升效能

### 7 天重掃
- 記錄 `last_full_scan` 時間
- 超過 7 天自動重新掃描
- 可偵測改款或新車型

### 錯誤處理
- 關鍵操作加入重試機制
- 隨機延遲避免被封鎖
- 詳細的錯誤記錄
- 優雅的中斷處理

## 維護與除錯

### 查看日誌
執行過程中的所有輸出都會顯示在終端機。

### 手動編輯進度
可直接編輯 `scrape_progress.json` 調整進度。

### 手動編輯資料庫
可使用 SQLite 工具（如 DB Browser for SQLite）直接編輯 `autobild_master.db`。

### 清除所有資料
刪除以下檔案：
- `autobild_master.db`
- `scrape_progress.json`
- `Brand_Exports/` 目錄

## 更新與擴展

### 新增品牌
系統會自動發現並處理新品牌。

### 修改批次大小
編輯 `scraper_config.py` 中的 `BATCH_SIZE` 設定。

### 修改重掃週期
編輯 `scraper_config.py` 中的 `FULL_RESCAN_DAYS` 設定。

### 修改延遲範圍
編輯 `scraper_config.py` 中的 `DELAY_MIN` 和 `DELAY_MAX` 設定。
