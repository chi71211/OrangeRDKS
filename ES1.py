import sys
# 防止終端機顯示中文時發生亂碼崩潰，遇到無法顯示的字元自動替換
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import sqlite3
import os
import time
import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# 🌟 進階防護：建立穩定的 Session 與自動重試機制
# ==========================================
session = requests.Session()

# 設定重試策略：總共重試 5 次。遇到 429 或伺服器錯誤時自動停頓重試
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

# 設定全域 Headers
session.headers.update({
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Connection": "keep-alive"
})

# ==========================================
# 1. API 請求基礎函式
# ==========================================
def get_manufacturers():
    url = "https://www.interpneu-raederkonfigurator.de/api/cars/manufacturers"
    res = session.get(url, timeout=15)
    return res.json() if res.status_code == 200 else []

def get_classes(brand):
    url = f"https://www.interpneu-raederkonfigurator.de/api/cars/classes?manufacturer={brand}"
    res = session.get(url, timeout=15)
    return res.json() if res.status_code == 200 else []

def get_type_groups(brand, car_class):
    url = "https://www.interpneu-raederkonfigurator.de/api/cars/type-groups"
    res = session.get(url, params={"manufacturer": brand, "class": car_class}, timeout=15)
    return res.json() if res.status_code == 200 else []

def get_versions(type_group):
    url = "https://www.interpneu-raederkonfigurator.de/api/cars/version-groups"
    res = session.get(url, params={"group": type_group}, timeout=15)
    return res.json() if res.status_code == 200 else []

def get_car_hsn_tsn(car_tag):
    url = "https://www.interpneu-raederkonfigurator.de/api/cars/car"
    res = session.get(url, params={"carTag": car_tag}, timeout=15)
    return res.json() if res.status_code == 200 else {}

def get_tpms(car_tag):
    url = "https://www.interpneu-raederkonfigurator.de/api/tpms/carTpms"
    res = session.get(url, params={"carTag": car_tag}, timeout=15)
    return res.json() if res.status_code == 200 else {}

def format_year(date_str):
    if not date_str or date_str == "0000-00-00":
        return "至今"
    return date_str[:7] 

# ==========================================
# 2. 資料庫輔助與轉檔函式
# ==========================================
def get_scraped_tags(db_name='RDKS.db'):
    """讀取資料庫，獲取所有已經抓取過的 carTag 集合"""
    if not os.path.exists(db_name):
        return set()
    try:
        conn = sqlite3.connect(db_name)
        df = pd.read_sql_query("SELECT carTag FROM tpms_sensors", conn)
        conn.close()
        return set(df['carTag'].astype(str).tolist())
    except:
        return set()

def auto_export_sql(db_name='RDKS.db', sql_name='RDKS_Backup.sql'):
    """將 SQLite 資料庫匯出成純文字的 .sql 檔案"""
    print(f"\n[轉檔] 準備將 {db_name} 轉換為純文字 {sql_name} 檔案...")
    if not os.path.exists(db_name):
        print(f"[錯誤] 找不到 {db_name}，無法轉檔！")
        return

    conn = sqlite3.connect(db_name)
    with open(sql_name, 'w', encoding='utf-8') as f:
        for line in conn.iterdump():
            f.write('%s\n' % line)
    conn.close()
    print(f"[完成] 🎉 已經成功自動產出 {sql_name} 備份檔！")

def save_batch_to_sql(batch_data, db_name='RDKS.db'):
    """獨立的批次存檔函式"""
    if not batch_data: return
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    values_list = [
        (r["carTag"], r["品牌"], r["車系"], r["型號版本"], r["年份區間"], r["HSN"], r["TSN"], r["OE感測器"])
        for r in batch_data
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO tpms_sensors 
        (carTag, 品牌, 車系, 型號版本, 年份區間, HSN, TSN, OE感測器) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', values_list)
    conn.commit()
    conn.close()

# ==========================================
# 3. 終極版：全面抓取主程式
# ==========================================
def main_scraper_all():
    folder_name = "RDKS"
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    # 設定每累積多少筆資料就存檔一次
    BATCH_SIZE = 50 

    brands = get_manufacturers()
    if not brands:
        print("[錯誤] 無法取得品牌清單。")
        return

    # --- 建立帶有「防重複護城河」的資料表 ---
    conn = sqlite3.connect('RDKS.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tpms_sensors (
            carTag TEXT,
            品牌 TEXT,
            車系 TEXT,
            型號版本 TEXT,
            年份區間 TEXT,
            HSN TEXT,
            TSN TEXT,
            OE感測器 TEXT,
            UNIQUE(carTag, OE感測器) 
        )
    ''')
    conn.commit()
    conn.close()

    # 讀取已經抓過的記憶
    scraped_tags = get_scraped_tags()
    print(f"[開始] 準備啟動！資料庫已有 {len(scraped_tags)} 筆車款紀錄。")
    print("-" * 50)

    for target_brand in brands:
        print(f"\n[執行中] 進入品牌：【{target_brand}】")
        
        batch_data = [] # 用來暫存這 50 筆資料的袋子
        total_brand_count = 0 # 紀錄這個品牌總共抓了幾筆

        classes = get_classes(target_brand)
        if not classes:
            continue

        for car_class in classes:
            type_groups = get_type_groups(target_brand, car_class)

            for tg_data in type_groups:
                tg_id = tg_data.get("group")
                if not tg_id: continue

                versions = get_versions(tg_id)
                for version in versions:
                    car_tag = str(version.get("tag") or version.get("carTag"))
                    if not car_tag: continue

                    # 第一道防線：如果這個車型抓過了，直接跳過
                    if car_tag in scraped_tags:
                        continue 

                    # ⚠️ 溫柔對待伺服器
                    time.sleep(0.3) 
                    
                    try:
                        car_details = get_car_hsn_tsn(car_tag)
                        hsn = car_details.get("hsn", "")
                        tsn = car_details.get("tsn", "")

                        tpms_data = get_tpms(car_tag)
                        oe_sensors = []
                        if isinstance(tpms_data, dict) and "tpms" in tpms_data:
                            for sensor in tpms_data["tpms"]:
                                if sensor.get("oeAm") == "O":
                                    oe_sensors.append(sensor.get("tpmsDescFrontend", ""))

                        year_from = format_year(version.get("productionFrom"))
                        year_to = format_year(version.get("productionTo"))

                        unique_oe_sensors = list(set(oe_sensors))
                        if not unique_oe_sensors:
                            unique_oe_sensors = [""]

                        for single_oe in unique_oe_sensors:
                            row_data = {
                                "carTag": car_tag,
                                "品牌": target_brand,
                                "車系": car_class,
                                "型號版本": version.get("version", ""),
                                "年份區間": f"{year_from} ~ {year_to}",
                                "HSN": hsn,
                                "TSN": tsn,
                                "OE感測器": single_oe
                            }
                            batch_data.append(row_data)
                            
                        # 更新記憶清單，確保不再抓取
                        scraped_tags.add(car_tag) 

                        # 🌟 重點：檢查袋子是不是裝滿 50 筆了？滿了就存進資料庫！
                        if len(batch_data) >= BATCH_SIZE:
                            save_batch_to_sql(batch_data)
                            total_brand_count += len(batch_data)
                            print(f"  💾 [批次存檔] 累積 {BATCH_SIZE} 筆，已安全寫入資料庫！ (車系: {car_class})")
                            batch_data = [] # 清空袋子，重新裝下一個 50 筆

                    except Exception as e:
                        print(f"⚠️ 抓取 {car_tag} 時發生異常，跳過此筆。錯誤訊息: {e}")
                        continue

            print(f"  ✅ 車系掃描完成: {car_class}")

        # 品牌迴圈結束後，把袋子裡剩餘沒滿 50 筆的資料也存進去
        if batch_data:
            save_batch_to_sql(batch_data)
            total_brand_count += len(batch_data)
            batch_data = []

        # 🌟 超級防漏機制：直接從資料庫把該品牌所有資料撈出來轉成 Excel
        print(f"  📊 [產出報表] 正在從資料庫撈取【{target_brand}】完整資料建立 Excel...")
        try:
            conn = sqlite3.connect('RDKS.db')
            # 撈出該品牌的所有資料 (防備之前可能中斷過的資料也能一起抓出來)
            df_brand = pd.read_sql_query("SELECT * FROM tpms_sensors WHERE 品牌=?", conn, params=(target_brand,))
            conn.close()

            if not df_brand.empty:
                excel_name = f"{folder_name}/{target_brand}_Data.xlsx"
                # 排除第一欄 carTag，不輸出到 Excel 給人看
                df_brand.drop(columns=['carTag'], inplace=True, errors='ignore')
                df_brand.to_excel(excel_name, index=False)
                print(f"  ✅ 【{target_brand}】Excel 匯出成功！目前庫內共有 {len(df_brand)} 筆。")
        except Exception as e:
            print(f"  ⚠️ 匯出 Excel 時發生錯誤: {e}")

        print("-" * 50)

    print("\n🎉 [完成] 所有品牌的資料爬取與更新檢查完畢！")

# ==========================================
# 4. 執行區塊 (終極一鍵啟動)
# ==========================================
if __name__ == "__main__":
    # 步驟 1：啟動主爬蟲 (會自動判斷進度、防重複並存檔)
    main_scraper_all()

    # 步驟 2：爬蟲結束後，自動將最新的資料庫匯出成 .sql 檔案
    auto_export_sql()
