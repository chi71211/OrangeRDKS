import sys
# 防止終端機顯示中文時發生亂碼崩潰，遇到無法顯示的字元自動替換
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import sqlite3
import os
import requests
import pandas as pd
import re
import json
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# 🌟 全域設定與檔案路徑
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, '胎壓偵測.db')
SQL_PATH = os.path.join(SCRIPT_DIR, '胎壓偵測.sql')
PROGRESS_FILE = os.path.join(SCRIPT_DIR, 'scrape_progress.json') # 新增：進度紀錄檔

session = requests.Session()
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

session.headers.update({
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Connection": "keep-alive"
})

# ==========================================
# 1. 進度與 7 天週期管理 (符合流程圖第一階段)
# ==========================================
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"cycle_start": time.time(), "last_brand": ""}

def save_progress(brand, completed=False):
    prog = load_progress()
    prog["last_brand"] = "" if completed else brand
    if completed:
        prog["cycle_start"] = time.time() # 任務全部完成，重置週期時間
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(prog, f)

def check_7_day_cycle():
    """檢查是否超過 7 天，超過則清除資料庫與進度啟動全面掃描"""
    prog = load_progress()
    now = time.time()
    # 7 天 = 7 * 24 * 3600 = 604800 秒
    if now - prog.get("cycle_start", now) > 604800:
        print("\n⏳ [週期檢查] 距離上次全面掃描已超過 7 天！啟動【全面檢查模式】...")
        print("   -> 正在清除舊資料庫與進度檔...")
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            conn.cursor().execute("DROP TABLE IF EXISTS tpms_sensors")
            conn.commit()
            conn.close()
        
        # 重置進度檔
        fresh_prog = {"cycle_start": now, "last_brand": ""}
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(fresh_prog, f)
        return "", True # last_brand="", is_new_cycle=True
    else:
        last_brand = prog.get("last_brand", "")
        if last_brand:
            print(f"\n⏳ [週期檢查] 7 天內，啟動【繼續進度模式】，準備從 {last_brand} 接續抓取...")
        return last_brand, False

# ==========================================
# 2. API 請求基礎函式
# ==========================================
def get_manufacturers():
    res = session.get("https://www.interpneu-raederkonfigurator.de/api/cars/manufacturers", timeout=15)
    return res.json() if res.status_code == 200 else []

def get_classes(brand):
    res = session.get(f"https://www.interpneu-raederkonfigurator.de/api/cars/classes?manufacturer={brand}", timeout=15)
    return res.json() if res.status_code == 200 else []

def get_type_groups(brand, car_class):
    res = session.get("https://www.interpneu-raederkonfigurator.de/api/cars/type-groups", params={"manufacturer": brand, "class": car_class}, timeout=15)
    return res.json() if res.status_code == 200 else []

def get_versions(type_group):
    res = session.get("https://www.interpneu-raederkonfigurator.de/api/cars/version-groups", params={"group": type_group}, timeout=15)
    return res.json() if res.status_code == 200 else []

def get_car_hsn_tsn(car_tag):
    res = session.get("https://www.interpneu-raederkonfigurator.de/api/cars/car", params={"carTag": car_tag}, timeout=15)
    return res.json() if res.status_code == 200 else {}

def get_tpms(car_tag):
    res = session.get("https://www.interpneu-raederkonfigurator.de/api/tpms/carTpms", params={"carTag": car_tag}, timeout=15)
    return res.json() if res.status_code == 200 else {}

def format_year(date_str):
    if not date_str or date_str == "0000-00-00":
        return "至今"
    return date_str[:7] 

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', '_', filename)

def find_key_value(d, keywords):
    """智能遞迴搜尋隱藏欄位"""
    if isinstance(d, dict):
        label = str(d.get("name", d.get("key", d.get("label", "")))).lower()
        if any(kw in label for kw in keywords) and ("value" in d or "val" in d):
            val = d.get("value", d.get("val", ""))
            if val and str(val).strip(): return str(val).strip()
        for k, v in d.items():
            k_lower = str(k).lower()
            if any(kw in k_lower for kw in keywords) and not isinstance(v, (dict, list)):
                if v is not None and str(v).strip(): return str(v).strip()
            res = find_key_value(v, keywords)
            if res: return res
    elif isinstance(d, list):
        for item in d:
            res = find_key_value(item, keywords)
            if res: return res
    return ""

# ==========================================
# 3. 資料庫輔助與排版轉檔函式
# ==========================================
def get_scraped_models():
    if not os.path.exists(DB_PATH): return set()
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT 品牌, 車系, 型號, 年份起點 FROM tpms_sensors", conn)
        conn.close()
        return set(tuple(str(x).strip() for x in row) for row in df.values)
    except:
        return set()

def auto_export_sql():
    if not os.path.exists(DB_PATH): return
    conn = sqlite3.connect(DB_PATH)
    with open(SQL_PATH, 'w', encoding='utf-8') as f:
        for line in conn.iterdump():
            f.write('%s\n' % line)
    conn.close()
    print(f"  [備份] 🎉 已自動產出 {os.path.basename(SQL_PATH)} 備份檔！")

def save_batch_to_sql(batch_data):
    if not batch_data: return
    df = pd.DataFrame(batch_data)
    columns_order = [
        '品牌', '車系', '型號', '年份起點', '年份終點', 'HSN', 'TSN', 
        '建設日期(Baujahr)', 'OE感測器', '廠商(Hersteller)', '頻率(Frequenz)'
    ]
    df = df.reindex(columns=columns_order).fillna("")
    
    group_cols = ['品牌', '車系', '型號', '年份起點', '年份終點', 'HSN', 'TSN']
    df_merged = df.groupby(group_cols, as_index=False).agg(
        lambda x: ', '.join(sorted(list(set(str(v) for v in x if str(v).strip()))))
    )
    df_merged = df_merged[columns_order] 
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executemany('''
        REPLACE INTO tpms_sensors 
        (品牌, 車系, 型號, 年份起點, 年份終點, HSN, TSN, "建設日期(Baujahr)", OE感測器, "廠商(Hersteller)", "頻率(Frequenz)") 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', df_merged.values.tolist())
    conn.commit()
    conn.close()

# ==========================================
# 4. 終極版：全面抓取主程式
# ==========================================
def main_scraper_all():
    folder_name = sanitize_filename("胎壓偵測")
    folder_path = os.path.join(SCRIPT_DIR, folder_name) 
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    BATCH_SIZE = 100 
    
    brands = get_manufacturers()
    if not brands: 
        print("[錯誤] 無法取得品牌清單。")
        return

    # 執行週期與進度檢查
    last_brand, is_new_cycle = check_7_day_cycle()
    skip_mode = bool(last_brand)

    # 建立資料表
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tpms_sensors (
            品牌 TEXT, 車系 TEXT, 型號 TEXT, 年份起點 TEXT, 年份終點 TEXT,
            HSN TEXT, TSN TEXT, "建設日期(Baujahr)" TEXT, OE感測器 TEXT,
            "廠商(Hersteller)" TEXT, "頻率(Frequenz)" TEXT,
            UNIQUE(品牌, 車系, 型號, 年份起點, HSN, TSN) 
        )
    ''')
    conn.commit()
    conn.close()

    scraped_models = get_scraped_models()
    print(f"\n[開始] 資料庫現有 {len(scraped_models)} 種世代紀錄。開始爬取...")
    print("-" * 50)

    for target_brand in brands:
        # 🌟 斷點接關機制：跳過已經處理過的品牌
        if skip_mode:
            if target_brand != last_brand:
                print(f"⏭️ [繼續進度] 已完成，跳過品牌: {target_brand}")
                continue
            else:
                skip_mode = False # 找到了上次中斷的品牌，解除跳過模式
                print(f"▶️ [繼續進度] 從 {target_brand} 恢復抓取！")

        print(f"\n[執行中] 進入品牌：【{target_brand}】")
        save_progress(target_brand) # 即時儲存目前進度
        batch_data = [] 

        classes = get_classes(target_brand)
        if not classes: continue

        for car_class in classes:
            type_groups = get_type_groups(target_brand, car_class)

            for tg_data in type_groups:
                tg_id = tg_data.get("group")
                if not tg_id: continue

                versions = get_versions(tg_id)
                versions.sort(key=lambda x: x.get('productionFrom', ''), reverse=True)
                
                already_exists_streak = 0 

                for idx, version in enumerate(versions):
                    car_tag = str(version.get("tag") or version.get("carTag"))
                    if not car_tag: continue

                    year_from = format_year(version.get("productionFrom"))
                    year_to = format_year(version.get("productionTo"))
                    model_version = version.get("version", "")
                    
                    model_identity = (str(target_brand).strip(), str(car_class).strip(), str(model_version).strip(), str(year_from).strip())

                    if model_identity in scraped_models:
                        if idx == 0:
                            # 🌟 強制檢查最新年份 (不管資料庫有沒有)
                            print(f"    🔄 [檢查更新] 型號 {tg_id} 最新年份，檢查是否有胎壓或年份變更...")
                            already_exists_streak = 0
                        else:
                            # 舊車款已存在，啟動連續跳過機制
                            already_exists_streak += 1
                            if already_exists_streak >= 5:
                                print(f"    ⏭️ [極速跳過] 型號 {tg_id} 連續 5 個舊年份皆無更新，略過剩餘舊車。")
                                break 
                            continue 
                    else:
                        already_exists_streak = 0

                    time.sleep(0.3) 
                    
                    try:
                        car_details = get_car_hsn_tsn(car_tag)
                        hsn = car_details.get("hsn", "")
                        tsn = car_details.get("tsn", "")

                        tpms_data = get_tpms(car_tag)
                        oe_sensors_info = []
                        
                        if isinstance(tpms_data, dict) and "tpms" in tpms_data:
                            for sensor in tpms_data["tpms"]:
                                if sensor.get("oeAm") == "O":
                                    hersteller = str(sensor.get("hersteller", ""))
                                    if not hersteller:
                                        hersteller = find_key_value(sensor, ['hersteller', 'manufacturer', 'brand', 'marke'])

                                    frequenz = str(sensor.get("frequenz", ""))
                                    if not frequenz:
                                        frequenz = find_key_value(sensor, ['frequenz', 'frequency', 'mhz'])
                                    if not frequenz: 
                                        s_dump = str(sensor).lower()
                                        if '433' in s_dump: frequenz = '433'
                                        elif '434' in s_dump: frequenz = '434'
                                        elif '315' in s_dump: frequenz = '315'

                                    baujahr = str(sensor.get("baujahr", ""))
                                    if not baujahr:
                                        baujahr = find_key_value(sensor, ['baujahr', 'production', 'year'])
                                    if not baujahr or baujahr == "0000-00-00": 
                                        baujahr = f"{year_from} ~ {year_to}"

                                    oe_sensors_info.append({
                                        "oe": str(sensor.get("tpmsDescFrontend", "")),
                                        "baujahr": baujahr,
                                        "hersteller": hersteller,
                                        "frequenz": frequenz
                                    })

                        if not oe_sensors_info:
                            oe_sensors_info = [{"oe": "", "baujahr": "", "hersteller": "", "frequenz": ""}]

                        for s_info in oe_sensors_info:
                            row_data = {
                                "品牌": target_brand,
                                "車系": car_class,
                                "型號": model_version,
                                "年份起點": year_from,
                                "年份終點": year_to,
                                "HSN": hsn,
                                "TSN": tsn,
                                "建設日期(Baujahr)": s_info["baujahr"],
                                "OE感測器": s_info["oe"],
                                "廠商(Hersteller)": s_info["hersteller"],
                                "頻率(Frequenz)": s_info["frequenz"]
                            }
                            batch_data.append(row_data)
                            
                        scraped_models.add(model_identity) 

                        if len(batch_data) >= BATCH_SIZE:
                            save_batch_to_sql(batch_data)
                            print(f"  💾 [批次合併存檔] 累積新車款已排版並安全寫入資料庫！ (車系: {car_class})")
                            batch_data = [] 

                    except Exception as e:
                        print(f"⚠️ 抓取異常，跳過此筆。錯誤訊息: {e}")
                        continue

            print(f"  ✅ 車系掃描完成: {car_class}")

        if batch_data:
            save_batch_to_sql(batch_data)
            batch_data = []

        # 🌟 單一品牌處理完畢：匯出 Excel
        try:
            conn = sqlite3.connect(DB_PATH)
            df_brand = pd.read_sql_query("SELECT * FROM tpms_sensors WHERE 品牌=?", conn, params=(target_brand,))
            conn.close()

            if not df_brand.empty:
                df_brand['年份'] = df_brand['年份起點'].astype(str) + " ~ " + df_brand['年份終點'].astype(str)
                columns_order = [
                    '品牌', '車系', '型號', '年份', 'HSN', 'TSN', 
                    '建設日期(Baujahr)', 'OE感測器', '廠商(Hersteller)', '頻率(Frequenz)'
                ]
                df_brand = df_brand.reindex(columns=columns_order)
                
                safe_brand_name = sanitize_filename(target_brand)
                excel_name = os.path.join(folder_path, f"{safe_brand_name}_Data.xlsx")
                df_brand.to_excel(excel_name, index=False)
                print(f"  📊 【{target_brand}】Excel 匯出成功！")
        except Exception as e:
            print(f"  ⚠️ 匯出 Excel 時發生錯誤: {e}")

        print("-" * 50)

    # 任務全數完成！清除進度、輸出最終 SQL
    print("\n🎉 [全部完成] 所有品牌的資料爬取與更新檢查完畢！")
    save_progress("", completed=True) # 標記為完成，重置進度
    auto_export_sql()

# ==========================================
# 執行區塊
# ==========================================
if __name__ == "__main__":
    main_scraper_all()