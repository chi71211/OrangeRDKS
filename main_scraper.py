"""
主爬蟲模組 - 整合進度管理、資料庫與爬蟲邏輯
"""
import asyncio
import random
import time
import nest_asyncio
nest_asyncio.apply()

from playwright.async_api import async_playwright
from progress_manager import ProgressManager
from database_manager import DatabaseManager
from scraper_config import *

class ProgressBar:
    """視覺化進度條"""
    def __init__(self, total: int, desc: str = ""):
        self.total = total
        self.current = 0
        self.desc = desc
        self.start_time = time.time()
        self.update(0)
    
    def update(self, n: int = 1):
        self.current += n
        self._display()
    
    def _display(self):
        if self.total == 0:
            return
        
        percent = (self.current / self.total) * 100
        bar_length = 30
        filled = int(bar_length * self.current / self.total)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        elapsed = time.time() - self.start_time
        if self.current > 0:
            eta = (elapsed / self.current) * (self.total - self.current)
            eta_str = f"ETA: {int(eta//60):02d}:{int(eta%60):02d}"
        else:
            eta_str = "ETA: --:--"
        
        print(f"\r    {self.desc} |{bar}| {self.current}/{self.total} ({percent:.1f}%) {eta_str}", end="", flush=True)
    
    def finish(self):
        elapsed = time.time() - self.start_time
        print(f"\n    ✅ 完成! 耗時: {int(elapsed//60):02d}:{int(elapsed%60):02d}")

class AutoBildScraper:
    def __init__(self):
        self.progress = ProgressManager(PROGRESS_FILE, FULL_RESCAN_DAYS)
        self.db = DatabaseManager(DB_FILE, CSV_EXPORT_DIR)
        self.batch_data = []
        self.browser = None
        self.page = None
    
    async def random_delay(self, min_delay: float = None, max_delay: float = None):
        """智慧隨機延遲，模擬人類行為"""
        if min_delay is None:
            min_delay = DELAY_MIN
        if max_delay is None:
            max_delay = DELAY_MAX
        
        # 基礎隨機延遲
        base_delay = random.uniform(min_delay, max_delay)
        
        # 偶爾加入較長停頓（模擬人類閱讀）
        if random.random() < 0.1:  # 10% 機率
            base_delay += random.uniform(1.0, 3.0)
        
        # 偶爾加入較短停頓（快速操作）
        if random.random() < 0.2:  # 20% 機率
            base_delay *= 0.5
        
        # 確保延遲在合理範圍內
        base_delay = max(0.3, min(base_delay, 5.0))
        
        await asyncio.sleep(base_delay)
    
    async def adaptive_delay(self, success: bool = True):
        """根據操作結果調整延遲"""
        if success:
            # 成功時使用較短延遲
            await self.random_delay(0.5, 1.2)
        else:
            # 失敗時使用較長延遲，避免被封鎖
            await self.random_delay(2.0, 4.0)
    
    async def setup_browser(self):
        """設定瀏覽器"""
        p = await async_playwright().start()
        self.browser = await p.chromium.launch(headless=True)
        self.page = await self.browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
    
    async def close_browser(self):
        """關閉瀏覽器"""
        if self.browser:
            await self.browser.close()
    
    async def handle_cookie_consent(self):
        """處理 Cookie 同意彈窗"""
        for attempt in range(3):
            try:
                iframe_selector = 'iframe[id^="sp_message_iframe"]'
                await self.page.wait_for_selector(iframe_selector, timeout=5000)
                frame = self.page.frame_locator(iframe_selector)
                await frame.get_by_role("button", name="Alle akzeptieren").click()
                print("   ✅ Cookie 同意")
                await asyncio.sleep(2)
                return True
            except Exception:
                await asyncio.sleep(1)
        return False
    
    async def save_batch(self):
        """儲存批次資料到資料庫"""
        if not self.batch_data:
            return
        
        inserted = self.db.insert_batch(self.batch_data)
        self.progress.update_stats(inserted)
        
        if inserted > 0:
            print(f"    💾 批次儲存: {inserted} 筆新紀錄")
        
        self.batch_data = []
    
    async def get_brand_links(self) -> list:
        """取得所有品牌連結"""
        print(f"🌐 前往總目錄: {CATALOG_URL}")
        await self.page.goto(CATALOG_URL, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        await self.handle_cookie_consent()
        
        await self.page.evaluate("window.scrollTo(0, 1000)")
        await asyncio.sleep(2)
        
        all_links = await self.page.query_selector_all("a[href*='/marken-modelle/']")
        brand_links = []
        seen_brand_urls = set()
        
        for el in all_links:
            href = await el.get_attribute('href')
            if href:
                full_url = href if href.startswith('http') else BASE_URL + href
                clean_url = full_url.split('#')[0].split('?')[0]
                
                if clean_url in [BASE_URL + "/marken-modelle", BASE_URL + "/marken-modelle/"]:
                    continue
                
                parts = clean_url.split('/')
                if len(parts) >= 5 and parts[3] == 'marken-modelle' and parts[4] != '':
                    brand_base_url = '/'.join(parts[:5]) + '/'
                    if brand_base_url not in seen_brand_urls:
                        brand_links.append(brand_base_url)
                        seen_brand_urls.add(brand_base_url)
        
        brand_links.sort(reverse=True)
        
        if TEST_MODE:
            brand_links = brand_links[:TEST_MAX_BRANDS]
        
        print(f"📋 找到 {len(brand_links)} 個品牌")
        return brand_links
    
    async def get_model_links(self, brand_url: str) -> list:
        """取得品牌下所有車系連結"""
        await self.page.goto(brand_url, timeout=60000, wait_until="domcontentloaded")
        await self.page.evaluate("window.scrollTo(0, 1500)")
        await asyncio.sleep(2)
        
        model_elements = await self.page.query_selector_all("a[href*='/marken-modelle/']")
        model_links = []
        seen_model_urls = set()
        brand_path_segments = [s for s in brand_url.replace(BASE_URL, '').split('/') if s]
        
        for el in model_elements:
            href = await el.get_attribute('href')
            if href:
                full_url = href if href.startswith('http') else BASE_URL + href
                clean_url = full_url.split('#')[0].split('?')[0]
                
                if clean_url.startswith(brand_url) and clean_url != brand_url:
                    model_segments = [s for s in clean_url.replace(BASE_URL, '').split('/') if s]
                    if len(model_segments) == len(brand_path_segments) + 1:
                        if not clean_url.endswith('/'):
                            clean_url += '/'
                        if clean_url not in seen_model_urls:
                            model_links.append(clean_url)
                            seen_model_urls.add(clean_url)
        
        model_links.sort()
        
        if TEST_MODE:
            model_links = model_links[:TEST_MAX_MODELS]
        
        return model_links
    
    async def expand_fuel_type_panel(self):
        """展開燃油類型面板"""
        await self.page.evaluate(r'''() => {
            const elements = Array.from(document.querySelectorAll('span, div, p, h1, h2, h3, h4, button'));
            const targets = elements.filter(el => el.innerText && el.innerText.includes('Kraftstoffart') && el.childElementCount === 0);
            targets.sort((a, b) => a.innerText.length - b.innerText.length);
            if (targets.length > 0) {
                try { targets[0].click(); } catch(e) {}
                try { if(targets[0].parentElement) targets[0].parentElement.click(); } catch(e) {}
            }
        }''')
        await asyncio.sleep(3)
    
    async def expand_basisdaten(self):
        """展開基礎數據區塊"""
        await self.page.evaluate(r'''() => {
            const elements = Array.from(document.querySelectorAll('span, div, h2, h3, h4, p, button'));
            const basisdatens = elements.filter(el => el.innerText && el.innerText.trim() === 'Basisdaten');
            basisdatens.forEach(b => {
                try { b.click(); } catch(e) {}
                try { if (b.parentElement) b.parentElement.click(); } catch(e) {}
            });
        }''')
        await asyncio.sleep(2)
    
    async def extract_car_data(self) -> dict:
        """擷取車輛資料"""
        return await self.page.evaluate(r'''() => {
            const leafNodes = Array.from(document.querySelectorAll('*')).filter(el => {
                if (el.children.length > 0) return false;
                const text = el.textContent.trim();
                if (!text) return false;
                if (el.closest('footer, nav, .footer')) return false;
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return false;
                return true;
            });

            const getValue = (labelName) => {
                const index = leafNodes.findIndex(el => {
                    const text = el.textContent.trim().toLowerCase().replace(/:$/, '');
                    return text === labelName.toLowerCase();
                });
                
                if (index !== -1 && index + 1 < leafNodes.length) {
                    const val = leafNodes[index + 1].textContent.trim();
                    if (val.length < 50) return val;
                }
                return 'N/A';
            };
            
            let hsn = getValue("HSN/TSN Schlüsselnummern");
            if (hsn === 'N/A' || hsn === '-') hsn = getValue("HSN/TSN");
            if (hsn === '-') hsn = 'N/A';

            return {
                "brand": getValue("Marke"),
                "model": getValue("Modell"),
                "variant": getValue("Typbezeichnung") || getValue("Ausstattung"),
                "year": getValue("Bauzeitraum"),
                "hsn_tsn": hsn
            };
        }''')
    
    async def click_variant(self, index: int, total: int) -> bool:
        """點擊特定款式"""
        if index == 0:
            try:
                target_locator = self.page.locator('.vvp__fuelType-dataBodyRow').nth(index)
                await target_locator.evaluate(r'''row => {
                    const arrow = row.querySelector('svg');
                    const link = row.querySelector('a');
                    if (arrow) {
                        arrow.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                        if (arrow.parentElement) arrow.parentElement.click();
                    } else if (link) {
                        link.click();
                    } else {
                        row.click();
                    }
                }''')
                return True
            except Exception:
                return False
        else:
            # 嘗試點擊「下一台」按鈕
            clicked_next = await self.page.evaluate(r'''() => {
                const buttons = Array.from(document.querySelectorAll('button, a, div[role="button"]'));
                const nextBtn = buttons.find(btn => {
                    const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                    const html = (btn.innerHTML || '').toLowerCase();
                    if (label.includes('nächste') || label.includes('weiter') || label.includes('next')) return true;
                    if ((html.includes('right') || html.includes('next')) && html.includes('<svg')) return true;
                    return false;
                });
                
                if (nextBtn) {
                    nextBtn.click();
                    return true;
                }
                return false;
            }''')
            
            if clicked_next:
                return True
            
            # 備用方案：返回列表重新點擊
            await self.page.go_back()
            await asyncio.sleep(1.5)
            try:
                target_locator = self.page.locator('.vvp__fuelType-dataBodyRow').nth(index)
                await target_locator.evaluate(r'''row => {
                    const arrow = row.querySelector('svg');
                    const link = row.querySelector('a');
                    if (arrow) {
                        arrow.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                        if (arrow.parentElement) arrow.parentElement.click();
                    } else if (link) {
                        link.click();
                    } else {
                        row.click();
                    }
                }''')
                return True
            except Exception:
                return False
    
    async def process_variant(self, brand_name: str, model_name: str, 
                              variant_index: int, total_variants: int) -> dict:
        """處理單一款式"""
        print(f"      👉 款式 {variant_index+1}/{total_variants}")
        
        if not await self.click_variant(variant_index, total_variants):
            return None
        
        await asyncio.sleep(4)
        await self.expand_basisdaten()
        
        car_data = await self.extract_car_data()
        
        # 整理資料
        brand = car_data.get("brand", "N/A")
        model = car_data.get("model", "N/A")
        variant = car_data.get("variant", "N/A")
        year = car_data.get("year", "N/A")
        hsn_tsn = car_data.get("hsn_tsn", "N/A")
        
        # 使用爬蟲取得的品牌/車型作為備用
        if brand == 'N/A' or len(brand) > 30:
            brand = brand_name
        if model == 'N/A' or len(model) > 50:
            model = model_name
        if len(year) > 30:
            year = "N/A"
        
        # 處理 HSN/TSN
        hsn = None
        tsn = None
        if hsn_tsn and hsn_tsn != 'N/A':
            parts = hsn_tsn.split('/')
            if len(parts) == 2:
                hsn = parts[0].strip()
                tsn = parts[1].strip()
            elif ',' in hsn_tsn:
                # 多組 HSN/TSN，返回多筆記錄
                codes = [c.strip() for c in hsn_tsn.split(',')]
                results = []
                for code in codes:
                    code_parts = code.split('/')
                    if len(code_parts) == 2:
                        results.append({
                            '廠牌': brand,
                            '車型': model,
                            '型號': variant,
                            '年份': year,
                            'HSN': code_parts[0].strip(),
                            'TSN': code_parts[1].strip(),
                            'HSN_TSN': code
                        })
                return results
        
        return {
            '廠牌': brand,
            '車型': model,
            '型號': variant,
            '年份': year,
            'HSN': hsn,
            'TSN': tsn,
            'HSN_TSN': hsn_tsn
        }
    
    async def process_model(self, brand_name: str, model_url: str) -> int:
        """處理單一車系，返回新增記錄數"""
        model_name = model_url.split('/')[-2].capitalize()
        
        print(f"  ↳ 車系: {model_name}")
        
        # 檢查是否應跳過
        if self.progress.should_skip_model(brand_name, model_name):
            print(f"    ⏭️ 略過（已完成）")
            return 0
        
        await self.page.goto(model_url, timeout=60000, wait_until="domcontentloaded")
        
        # 滾動載入
        await self.page.evaluate(r'''async () => {
            await new Promise((resolve) => {
                let totalHeight = 0; let distance = 300;
                let timer = setInterval(() => {
                    window.scrollBy(0, distance); totalHeight += distance;
                    if (totalHeight >= document.body.scrollHeight - window.innerHeight || totalHeight > 10000) {
                        clearInterval(timer); resolve();
                    }
                }, 100);
            });
        }''')
        
        await self.expand_fuel_type_panel()
        
        target_count = await self.page.locator('.vvp__fuelType-dataBodyRow').count()
        
        if target_count == 0:
            print(f"    ❌ 找不到款式")
            self.progress.mark_model_completed(brand_name, model_name)
            return 0
        
        print(f"    📦 共 {target_count} 個款式")
        
        # 建立進度條
        variant_progress = ProgressBar(target_count, f"處理款式")
        
        new_records = 0
        
        for i in range(target_count):
            if TEST_MODE and i >= TEST_MAX_VARIANTS:
                break
            
            result = await self.process_variant(brand_name, model_name, i, target_count)
            
            if result is None:
                variant_progress.update()
                await self.adaptive_delay(success=False)
                continue
            
            # 處理結果（可能是單筆或列表）
            if isinstance(result, list):
                for record in result:
                    self.batch_data.append(record)
                new_records += len(result)
            else:
                self.batch_data.append(result)
                new_records += 1
            
            # 檢查是否需要儲存批次
            if len(self.batch_data) >= BATCH_SIZE:
                await self.save_batch()
            
            variant_progress.update()
            await self.adaptive_delay(success=True)
        
        variant_progress.finish()
        
        self.progress.mark_model_completed(brand_name, model_name)
        
        return new_records
    
    async def process_brand(self, brand_url: str) -> int:
        """處理單一品牌，返回新增記錄數"""
        brand_name = brand_url.split('/')[-2].upper()
        
        print(f"\n{'='*50}")
        print(f"🏭 品牌: {brand_name}")
        print(f"{'='*50}")
        
        # 檢查是否應跳過
        if self.progress.should_skip_brand(brand_name):
            print(f"  ⏭️ 略過（已完成）")
            return 0
        
        self.progress.set_current_position(brand=brand_name)
        
        model_links = await self.get_model_links(brand_url)
        print(f"  📋 共 {len(model_links)} 個車系")
        
        # 建立品牌進度條
        brand_progress = ProgressBar(len(model_links), f"處理 {brand_name}")
        
        brand_total = 0
        
        for idx, model_url in enumerate(model_links):
            result = await self.process_model(brand_name, model_url)
            brand_total += result
            brand_progress.update()
        
        brand_progress.finish()
        
        # 品牌完成，匯出 CSV 並更新統計
        self.db.update_brand_stats(brand_name)
        self.db.export_brand_csv(brand_name)
        
        self.progress.mark_brand_completed(brand_name)
        
        print(f"  📊 品牌 {brand_name} 統計: 共 {brand_total} 筆新紀錄")
        
        return brand_total
    
    async def run(self):
        """執行爬蟲"""
        print("\n" + "="*60)
        print("🚀 AutoBild 型錄爬蟲啟動")
        print("="*60)
        
        # 顯示目前進度
        resume_pos = self.progress.get_resume_position()
        self.progress.print_summary()
        
        try:
            await self.setup_browser()
            
            brand_links = await self.get_brand_links()
            
            # 確定起始位置
            start_index = 0
            if resume_pos['brand'] and not resume_pos['need_rescan']:
                for idx, url in enumerate(brand_links):
                    if resume_pos['brand'] in url:
                        start_index = idx
                        print(f"\n📍 從上次中斷處繼續: {resume_pos['brand']}")
                        break
            
            # 建立總進度條
            total_brands = len(brand_links) - start_index
            main_progress = ProgressBar(total_brands, "總進度")
            
            # 遍歷品牌
            for idx in range(start_index, len(brand_links)):
                brand_url = brand_links[idx]
                brand_name = brand_url.split('/')[-2].upper()
                
                print(f"\n[{idx+1}/{len(brand_links)}] 處理品牌: {brand_name}")
                
                await self.process_brand(brand_url)
                main_progress.update()
            
            main_progress.finish()
            
            # 最終儲存剩餘批次
            await self.save_batch()
            
            # 全面掃描完成
            if self.progress.need_full_rescan():
                self.progress.mark_full_scan_complete()
                print("\n✅ 全面掃描完成！")
            
            # 顯示最終統計
            self.progress.print_summary()
            self.db.print_summary()
            
        except KeyboardInterrupt:
            print("\n\n⚠️ 使用者中斷！進度已自動儲存。")
            await self.save_batch()
            self.progress.save()
            
        except Exception as e:
            print(f"\n❌ 執行錯誤: {e}")
            import traceback
            traceback.print_exc()
            await self.save_batch()
            self.progress.save()
            
        finally:
            await self.close_browser()
            self.db.close()
            
            print("\n" + "="*60)
            print("📊 最終狀態")
            print("="*60)
            print(f"  進度檔案: {PROGRESS_FILE}")
            print(f"  資料庫: {DB_FILE}")
            print(f"  CSV 目錄: {CSV_EXPORT_DIR}")
            print("="*60)


async def main():
    scraper = AutoBildScraper()
    await scraper.run()


if __name__ == "__main__":
    asyncio.run(main())
