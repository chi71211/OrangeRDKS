"""
測試腳本 - 驗證所有模組是否正常運作
"""
import sys
import os

def test_imports():
    """測試所有模組是否可以正常匯入"""
    print("測試模組匯入...")
    
    try:
        import scraper_config
        print("  ✅ scraper_config.py")
    except Exception as e:
        print(f"  ❌ scraper_config.py: {e}")
        return False
    
    try:
        from progress_manager import ProgressManager
        print("  ✅ progress_manager.py")
    except Exception as e:
        print(f"  ❌ progress_manager.py: {e}")
        return False
    
    try:
        from database_manager import DatabaseManager
        print("  ✅ database_manager.py")
    except Exception as e:
        print(f"  ❌ database_manager.py: {e}")
        return False
    
    try:
        from main_scraper import AutoBildScraper, ProgressBar
        print("  ✅ main_scraper.py")
    except Exception as e:
        print(f"  ❌ main_scraper.py: {e}")
        return False
    
    return True

def test_progress_bar():
    """測試進度條功能"""
    print("\n測試進度條功能...")
    
    try:
        from main_scraper import ProgressBar
        import time
        
        # 建立進度條
        progress = ProgressBar(10, "測試進度")
        
        # 模擬處理
        for i in range(10):
            time.sleep(0.1)
            progress.update()
        
        progress.finish()
        print("  ✅ 進度條功能正常")
        return True
    except Exception as e:
        print(f"  ❌ 進度條測試失敗: {e}")
        return False

def test_database():
    """測試資料庫功能"""
    print("\n測試資料庫功能...")
    
    try:
        from database_manager import DatabaseManager
        import tempfile
        import os
        
        # 建立臨時資料庫
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        db = DatabaseManager(db_path, tempfile.mkdtemp())
        
        # 測試插入
        result = db.insert_record(
            brand="TEST",
            model="Model1",
            variant="Variant1",
            year="2024",
            hsn="123",
            tsn="456"
        )
        
        if result:
            print("  ✅ 資料插入成功")
        else:
            print("  ❌ 資料插入失敗")
            return False
        
        # 測試去重
        result2 = db.insert_record(
            brand="TEST",
            model="Model1",
            variant="Variant1",
            year="2024",
            hsn="123",
            tsn="456"
        )
        
        if not result2:
            print("  ✅ 去重功能正常")
        else:
            print("  ❌ 去重功能失敗")
            return False
        
        # 測試查詢
        count = db.get_total_count()
        if count == 1:
            print("  ✅ 查詢功能正常")
        else:
            print(f"  ❌ 查詢功能異常，期望 1，實際 {count}")
            return False
        
        db.close()
        
        # 清理臨時檔案
        os.unlink(db_path)
        
        return True
    except Exception as e:
        print(f"  ❌ 資料庫測試失敗: {e}")
        return False

def test_progress_manager():
    """測試進度管理功能"""
    print("\n測試進度管理功能...")
    
    try:
        from progress_manager import ProgressManager
        import tempfile
        import os
        
        # 建立臨時進度檔案
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            progress_path = f.name
        
        pm = ProgressManager(progress_path, 7)
        
        # 測試設定位置
        pm.set_current_position(brand="TEST", model="Model1")
        
        # 測試標記完成
        pm.mark_model_completed("TEST", "Model1")
        pm.mark_brand_completed("TEST")
        
        # 測試查詢
        if pm.should_skip_brand("TEST"):
            print("  ✅ 品牌跳過功能正常")
        else:
            print("  ❌ 品牌跳過功能失敗")
            return False
        
        if pm.should_skip_model("TEST", "Model1"):
            print("  ✅ 車系跳過功能正常")
        else:
            print("  ❌ 車系跳過功能失敗")
            return False
        
        # 清理臨時檔案
        os.unlink(progress_path)
        
        return True
    except Exception as e:
        print(f"  ❌ 進度管理測試失敗: {e}")
        return False

def main():
    """主測試函數"""
    print("="*50)
    print("AutoBild 爬蟲系統 - 模組測試")
    print("="*50)
    
    all_passed = True
    
    # 測試模組匯入
    if not test_imports():
        all_passed = False
    
    # 測試進度條
    if not test_progress_bar():
        all_passed = False
    
    # 測試資料庫
    if not test_database():
        all_passed = False
    
    # 測試進度管理
    if not test_progress_manager():
        all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("✅ 所有測試通過！")
        print("系統已準備就緒，可以執行 python run.py 開始爬蟲。")
    else:
        print("❌ 部分測試失敗，請檢查錯誤訊息。")
    print("="*50)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
