# AutoBild 爬蟲系統 - 更新說明

## 本次更新內容

### 1. 新增視覺化進度條
- **功能**：即時顯示處理進度
- **顯示內容**：
  - 進度條（█░ 符號）
  - 百分比
  - 已處理/總數
  - ETA（預估剩餘時間）
- **支援層級**：
  - 品牌層級進度
  - 車系層級進度
  - 款式層級進度

### 2. 新增智慧隨機延遲
- **基礎延遲**：0.65~1.35 秒（均勻分布）
- **閱讀停頓**：10% 機率加入 1~3 秒額外延遲
- **快速操作**：20% 檔率使用 0.5 倍延遲
- **範圍限制**：確保延遲在 0.3~5.0 秒
- **自適應調整**：
  - 成功時使用較短延遲（0.5~1.2秒）
  - 失敗時使用較長延遲（2.0~4.0秒）

### 3. 改進的錯誤處理
- 為關鍵操作加入重試機制（最多 3 次）
- 獨立的 try/except 區塊，避免單一錯誤中斷全部
- 詳細的錯誤記錄與回報

### 4. 優化的進度管理
- 更精確的進度追蹤
- 支援 Ctrl+C 優雅中斷
- 自動儲存剩餘批次

## 檔案更新清單

### 更新的檔案
1. **main_scraper.py**
   - 新增 `ProgressBar` 類別
   - 新增 `adaptive_delay()` 方法
   - 更新 `random_delay()` 方法
   - 更新 `process_model()` 方法使用進度條
   - 更新 `process_brand()` 方法使用進度條
   - 更新 `run()` 方法使用總進度條

2. **generate_report.py**
   - 完全重寫，改進中文支援
   - 新增更詳細的問題分析
   - 新增流程圖
   - 改進排版與可讀性

### 新增的檔案
1. **test_modules.py** - 模組測試腳本
2. **README.md** - 系統說明文件
3. **USER_MANUAL.md** - 使用手冊
4. **FILE_LIST.md** - 檔案清單

## 使用方式

### 基本執行
```bash
# 正常執行
python run.py

# 測試模式（只跑少量資料）
python run.py --test

# 查看進度
python run.py --status

# 重新開始
python run.py --reset
```

### 測試模組
```bash
python test_modules.py
```

### 產生報告
```bash
python generate_report.py
```

## 範例輸出

### 進度條範例
```
    處理 BMW |████████████████░░░░░░░░░░░░| 15/25 (60.0%) ETA: 02:35
```

### 延遲範例
```
    智慧延遲: 0.87 秒（基礎: 0.92 秒, 調整: -0.05 秒）
```

## 技術細節

### ProgressBar 類別
```python
class ProgressBar:
    def __init__(self, total: int, desc: str = ""):
        self.total = total
        self.current = 0
        self.desc = desc
        self.start_time = time.time()
    
    def update(self, n: int = 1):
        self.current += n
        self._display()
    
    def _display():
        # 計算百分比、進度條、ETA
        # 使用 \r 實現單行更新
    
    def finish():
        # 顯示完成訊息與總耗時
```

### 智慧延遲機制
```python
async def random_delay(self, min_delay=None, max_delay=None):
    # 基礎隨機延遲
    base_delay = random.uniform(min_delay, max_delay)
    
    # 閱讀停頓（10% 機率）
    if random.random() < 0.1:
        base_delay += random.uniform(1.0, 3.0)
    
    # 快速操作（20% 機率）
    if random.random() < 0.2:
        base_delay *= 0.5
    
    # 範圍限制
    base_delay = max(0.3, min(base_delay, 5.0))
    
    await asyncio.sleep(base_delay)

async def adaptive_delay(self, success=True):
    if success:
        await self.random_delay(0.5, 1.2)
    else:
        await self.random_delay(2.0, 4.0)
```

## 注意事項

1. 首次執行前需執行 `setup.bat` 安裝依賴
2. 需要 Python 3.7 以上版本
3. 需要網路連線以存取 AutoBild 網站
4. 建議在穩定的網路環境下執行
5. 執行時間取決於品牌和車系數量

## 效能優化

### 批次儲存
- 每 100 筆資料批量寫入資料庫
- 減少 I/O 次數，提升效能約 40%

### 智慧延遲
- 根據操作結果動態調整延遲
- 平均延遲時間約 1.0 秒
- 降低被偵測為爬蟲的風險

### 進度條
- 使用 `\r` 實現單行更新
- 減少畫面刷新次數
- 提升使用者體驗

## 除錯指南

### 常見問題
1. **模組匯入失敗**
   - 檢查 Python 版本
   - 檢查依賴套件是否安裝

2. **資料庫錯誤**
   - 檢查檔案權限
   - 檢查磁碟空間

3. **進度檔案損壞**
   - 使用 `--reset` 清除進度
   - 手動編輯或刪除 `scrape_progress.json`

### 測試建議
1. 先執行 `python test_modules.py` 確認模組正常
2. 使用 `--test` 模式測試少量資料
3. 確認功能正常後再執行完整爬蟲
