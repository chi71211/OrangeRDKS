# AutoBild 爬蟲系統 - 檔案清單

## 核心模組

| 檔案名稱 | 說明 | 大小 |
|---------|------|------|
| `scraper_config.py` | 配置設定檔，包含所有可調整參數 | ~1KB |
| `progress_manager.py` | 進度管理模組，處理斷點續傳 | ~4KB |
| `database_manager.py` | 資料庫管理模組，處理去重與批次寫入 | ~5KB |
| `main_scraper.py` | 主爬蟲邏輯，整合所有功能 | ~10KB |

## 執行檔

| 檔案名稱 | 說明 | 用途 |
|---------|------|------|
| `run.py` | 命令列執行入口 | 支援 `--test`, `--status`, `--reset` 參數 |
| `setup.bat` | 初次設定腳本 | 自動安裝依賴並產生報告 |
| `generate_report.bat` | 報告產生腳本 | 產生 PDF 報告 |

## 報告與文件

| 檔案名稱 | 說明 |
|---------|------|
| `generate_report.py` | 報告產生器，產生 PDF 與流程圖 |
| `AutoBild_爬蟲問題與解決方案.pdf` | 完整問題分析與解決方案報告 |
| `flowchart.png` | 系統架構流程圖 |
| `README.md` | 系統說明文件 |
| `USER_MANUAL.md` | 使用手冊 |

## 設定檔

| 檔案名稱 | 說明 |
|---------|------|
| `requirements.txt` | Python 依賴套件清單 |

## 執行時產生的檔案

| 檔案名稱 | 說明 |
|---------|------|
| `autobild_master.db` | SQLite 資料庫 |
| `scrape_progress.json` | 進度檔案 |
| `Brand_Exports/` | CSV 匯出目錄 |

## 快速開始

1. **初次設定**：雙擊 `setup.bat`
2. **執行爬蟲**：`python run.py`
3. **查看進度**：`python run.py --status`
4. **重新開始**：`python run.py --reset`

## 檔案依賴關係

```
run.py
  ├── scraper_config.py
  ├── progress_manager.py
  ├── database_manager.py
  └── main_scraper.py
        ├── scraper_config.py
        ├── progress_manager.py
        └── database_manager.py

generate_report.py
  └── (獨立執行)

setup.bat
  ├── requirements.txt
  └── generate_report.py
```

## 注意事項

1. 首次執行前需執行 `setup.bat` 安裝依賴
2. 需要 Python 3.7 以上版本
3. 需要網路連線以存取 AutoBild 網站
4. 執行時間取決於品牌和車系數量
5. 建議在穩定的網路環境下執行
