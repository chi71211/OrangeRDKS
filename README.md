🚗 胎壓偵測器 (TPMS) 自動爬蟲系統

這是一個專為抓取、彙整汽車胎壓感測器資料所設計的自動化爬蟲系統。具備防封鎖、斷點接關、7天自動重置與資料自動排版合併等企業級進階功能。

💡 系統運作原理剖析

本爬蟲系統並非單純的「從頭抓到尾」，而是設計為一個具備狀態記憶的循環系統。其核心運作方式可分為三個層次：

週期性大掃除 (7-Day Cycle)：
目標網站的資料會不定期更新。系統會檢查上次完整執行時間，若超過 7 天，系統會啟動「全面掃描模式」，保留舊資料庫的同時，從第一個品牌開始重新地毯式比對，確保抓下所有原廠的新增或修正。

精準斷點接關 (Smart Resume)：
若在 7 天內被排程喚醒（或手動重啟），系統會讀取 scrape_progress.json。透過精確到「品牌 > 車系 > 型號」的記憶點，程式能在一秒內 continue 略過已完成的區塊，直接抵達中斷點繼續執行，達到資源零浪費。

無損寫入與聚合 (Upsert & Aggregation)：
為了避免資料重複，系統不依賴簡單的 Append，而是利用 SQLite 的 REPLACE INTO 語法，以「品牌、車系、型號、年份起點、HSN、TSN」為唯一鍵值 (Unique Key)。當遇到相同車款但感測器更新時，系統會自動覆寫舊資料，保證庫內資料永遠是最新的唯一版本。

🛡️ 技術挑戰與解決方案 (Technical Hurdles)

在開發這套爬蟲的過程中，我們遇到了幾個棘手的技術難點，並成功透過工程架構解決：

難點一：如何避免抓到一半斷線，導致前功盡棄？

問題描述： 目標網站包含數十個品牌、上千種車系，全部掃描一次需要數小時。如果在第 4 個小時遇到網路不穩或伺服器出錯，從頭重抓的時間成本太高。

解決方案 (三層進度記憶)： 我們實作了 save_progress() 函式，在迴圈深入到「Type Group (型號)」層級時即時存檔。即使程式被強制關閉，下次啟動時也會讀取 last_brand、last_class、last_tg，實現無縫接關。

難點二：跨車系、跨品牌的「資料污染」問題

問題描述： 為了降低資料庫寫入頻率，系統採用了 batch_data (批次佇列)，累積滿 80 筆才寫入。但這導致一個致命風險：如果在切換「車系」或「品牌」時，佇列裡剛好剩下 79 筆資料，這些資料會被錯誤地帶進下一個車系的迴圈中。

解決方案 (強制殘留清理)： 在每個 car_class 迴圈結束的尾端，加入嚴格的 if batch_data: 檢查。只要有殘留資料，強制執行 save_batch_to_sql 並 clear() 佇列，徹底杜絕跨車系的資料污染。

難點三：同一車款存在多種感測器，導致 Excel 暴增重複列

問題描述： 某些車款（如 BMW X5）可能同時支援 433MHz 與 315MHz 的感測器，或由不同廠商製造。如果直接寫入，Excel 報表中會出現好幾行完全一樣的車，只有「頻率」那一格不同，嚴重影響閱讀與後續匯入 ERP 的排版。

解決方案 (Pandas 預先聚合)： 在寫入 SQLite 之前，先使用 Pandas 的 .groupby() 將相同車款 (HSN/TSN) 的資料群組化。對於差異欄位（如 OE感測器、廠商、頻率），使用 lambda x: ', '.join(...) 進行逗號串接與去重。最終讓 Excel 呈現出完美的「一行一車」整潔版面。

難點四：極易觸發的反爬蟲機制 (Rate Limiting)

問題描述： 網站對於密集的 API 請求有嚴格的限制（會回傳 HTTP 429 錯誤），若不理會繼續發送，IP 將會被封鎖。

解決方案 (退避策略與隨機延遲)：

導入 urllib3 的 Retry 模組，將 backoff_factor 設定為 1.5，遇到 5xx 錯誤時自動指數級延長重試時間。

在每次請求前加入 time.sleep(random.uniform(0.65, 1.35))，模擬人類操作的隨機停頓。

封裝 safe_json_get()，若真的不幸撞到 429 限制，強制讓程式「冷卻 10 秒」，確保爬蟲的長期存活率。

## 📊 系統運作流程圖

本系統的核心運作邏輯如下圖所示：

# RDKS 自動爬蟲系統 - 完整運作流程圖

```mermaid
flowchart TD
    Start([啟動爬蟲]) 
    --> LoadProg[讀取 scrape_progress.json]
    
    LoadProg 
    --> Check7Days{距離上次全面掃描<br>是否超過 7 天?}
    
    Check7Days -- 是 --> FullMode[全面掃描模式<br>保留歷史資料]
    Check7Days -- 否 --> ResumeMode[繼續模式<br>讀取斷點]
    
    FullMode & ResumeMode 
    --> SetupDB[建立/檢查 SQLite 資料表]
    
    SetupDB 
    --> InitBatch[初始化 batch_data]
    
    InitBatch 
    --> BrandLoop[遍歷所有品牌]
    
    BrandLoop 
    --> CheckSkipBrand{是否在跳過模式?}
    
    CheckSkipBrand -- 是 --> SkipBrand[跳過此品牌] 
    SkipBrand --> BrandLoop
    
    CheckSkipBrand -- 否 --> SaveBrandProg[儲存品牌進度]
    SaveBrandProg --> ClassLoop[遍歷車系]
    
    ClassLoop 
    --> CheckSkipClass{是否在跳過模式?}
    
    CheckSkipClass -- 是 --> SkipClass[跳過此車系] 
    SkipClass --> ClassLoop
    
    CheckSkipClass -- 否 --> TGLoop[遍歷 Type Group]
    
    TGLoop 
    --> SaveTGProg[儲存 TG 進度]
    SaveTGProg 
    --> VersionLoop[版本迴圈<br>新→舊排序]
    
    VersionLoop 
    --> RandomSleep[隨機延遲 0.65~1.35 秒]
    
    RandomSleep 
    --> SafeAPI[safe_json_get<br>取得車輛與 TPMS 資料]
    
    SafeAPI 
    --> Parse[解析感測器資料<br>find_key_value]
    
    Parse 
    --> AddToBatch[加入 batch_data]
    
    AddToBatch 
    --> CheckBatchSize{batch_data >= 80 筆?}
    
    CheckBatchSize -- 是 --> SaveDB[save_batch_to_sql<br>Pandas聚合 + REPLACE]
    SaveDB --> ClearBatch[清除 batch_data]
    ClearBatch --> VersionLoop
    
    CheckBatchSize -- 否 --> VersionLoop
    
    VersionLoop -- 車系結束 --> FinalFlush{還有殘留資料?}
    FinalFlush -- 是 --> SaveResidual[強制存檔清理]
    SaveResidual --> ClassLoop
    FinalFlush -- 否 --> ClassLoop
    
    ClassLoop -- 品牌結束 --> ExportExcel[匯出該品牌 Excel]
    ExportExcel --> BrandLoop
    
    BrandLoop -- 全部完成 --> Finalize[標記完成<br>清除進度]
    Finalize --> ExportSQL[產出 SQL 備份]
    ExportSQL --> End([程式結束])
