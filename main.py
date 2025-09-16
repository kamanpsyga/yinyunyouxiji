#!/usr/bin/env python3
"""
HidenCloud 自动登录脚本
使用 Playwright 自动化登录到 https://dash.hidencloud.com
"""

import os
import sys
import time
import logging
from typing import Optional
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志（只输出到控制台）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class HidenCloudLogin:
    """HidenCloud 自动登录"""
    
    def __init__(self):
        self.base_url = "https://dash.hidencloud.com"
        self.login_url = "https://dash.hidencloud.com/auth/login"
        
        # 加载服务器配置
        self.servers = self._load_server_config()
        
        # 从环境变量获取 Cookie 值
        self.cookie_value = os.getenv('REMEMBER_WEB_COOKIE')
        if not self.cookie_value:
            raise ValueError("请设置环境变量 REMEMBER_WEB_COOKIE")
        
        if not self.servers:
            raise ValueError("请设置环境变量 HIDENCLOUD_SERVERS")
    
    def _load_server_config(self):
        """从环境变量加载服务器配置"""
        try:
            server_json = os.getenv('HIDENCLOUD_SERVERS')
            if not server_json:
                logger.error("未设置环境变量 HIDENCLOUD_SERVERS")
                return []
            
            import json
            servers = json.loads(server_json)
            logger.info(f"从环境变量加载 {len(servers)} 个服务器配置")
            return servers
            
        except json.JSONDecodeError as e:
            logger.error(f"服务器配置JSON解析失败: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"加载服务器配置失败: {str(e)}")
            return []
    
    def _take_screenshot(self, page: Page, server_name: str):
        """截图保存到 img 文件夹"""
        try:
            # 确保 img 文件夹存在
            os.makedirs('img', exist_ok=True)
            
            # 等待 CF 验证完成和页面完全加载
            logger.info("等待 Cloudflare 验证和页面加载完成...")
            time.sleep(15)  # 等待15秒让CF验证完成
            
            # 尝试等待页面网络空闲状态，但不强制要求
            try:
                page.wait_for_load_state('networkidle', timeout=60000)  # 增加到60秒
                logger.info("页面网络空闲状态达成")
            except Exception as e:
                logger.warning(f"等待网络空闲超时，继续截图: {str(e)}")
            
            # 再等待几秒确保页面渲染完成
            time.sleep(5)
            
            # 生成截图文件名
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            filename = f"img/login_success_{server_name}_{timestamp}.png"
            
            # 截图
            page.screenshot(path=filename, full_page=True)  # 添加全页面截图
            logger.info(f"📸 截图已保存: {filename}")
            
        except Exception as e:
            logger.error(f"截图保存失败: {str(e)}")
            # 尝试简单截图作为备用
            try:
                timestamp = time.strftime('%Y%m%d_%H%M%S')
                filename = f"img/fallback_{server_name}_{timestamp}.png"
                page.screenshot(path=filename)
                logger.info(f"📸 备用截图已保存: {filename}")
            except Exception as fallback_e:
                logger.error(f"备用截图也失败: {str(fallback_e)}")
    
    def _handle_cloudflare_verification(self, page: Page):
        """处理 Cloudflare 人机验证"""
        try:
            logger.info("正在检查 Cloudflare 验证...")
            
            # 等待页面稳定
            time.sleep(3)
            
            # 查找 Cloudflare 验证复选框
            checkbox_selectors = [
                'label.cb-lb input[type="checkbox"]',  # 根据实际结构：label.cb-lb 内的 checkbox
                'label:has-text("Verify you are human") input[type="checkbox"]'  # 英文版本
            ]
            
            checkbox_found = False
            
            # 也尝试直接点击 label 标签
            label_selectors = [
                'label.cb-lb',                                    # 直接点击 label
                'label:has-text("Verify you are human")'          # 英文版本
            ]
            
            # 先尝试点击复选框
            for selector in checkbox_selectors:
                try:
                    checkbox = page.locator(selector).first
                    if checkbox.is_visible(timeout=5000):
                        logger.info(f"找到 Cloudflare 验证复选框: {selector}")
                        
                        # 滚动到元素可见位置
                        checkbox.scroll_into_view_if_needed()
                        time.sleep(1)
                        
                        # 点击复选框
                        checkbox.click()
                        logger.info("✅ 已点击 Cloudflare 验证复选框")
                        checkbox_found = True
                        break
                except Exception as e:
                    logger.info(f"选择器 {selector} 未找到复选框: {str(e)}")
                    continue
            
            # 如果复选框点击失败，尝试点击 label
            if not checkbox_found:
                logger.info("尝试点击 label 标签...")
                for selector in label_selectors:
                    try:
                        label = page.locator(selector).first
                        if label.is_visible(timeout=5000):
                            logger.info(f"找到 Cloudflare 验证标签: {selector}")
                            
                            # 滚动到元素可见位置
                            label.scroll_into_view_if_needed()
                            time.sleep(1)
                            
                            # 点击标签
                            label.click()
                            logger.info("✅ 已点击 Cloudflare 验证标签")
                            checkbox_found = True
                            break
                    except Exception as e:
                        logger.info(f"选择器 {selector} 未找到标签: {str(e)}")
                        continue
            
            if checkbox_found:
                # 等待验证完成
                logger.info("等待 Cloudflare 验证完成...")
                time.sleep(15)  # 增加等待时间到15秒
                
                # 检查验证是否真的完成
                max_attempts = 6  # 最多等待30秒（6次 * 5秒）
                for attempt in range(max_attempts):
                    current_url = page.url
                    logger.info(f"检查验证状态 (第{attempt+1}次): {current_url}")
                    
                    # 检查是否还有验证元素
                    try:
                        verification_text = page.locator('text="Verify you are human"').first
                        if not verification_text.is_visible(timeout=2000):
                            logger.info("✅ Cloudflare 验证已完成，验证文本消失")
                            break
                        else:
                            logger.info("验证页面仍然存在，继续等待...")
                    except:
                        logger.info("✅ 验证元素不可见，可能已通过验证")
                        break
                    
                    if attempt < max_attempts - 1:
                        time.sleep(5)
                
            if not checkbox_found:
                logger.info("未找到 Cloudflare 验证复选框，可能已经通过验证")
            
            # 最终检查页面状态
            current_url = page.url
            if "dash.hidencloud.com" in current_url and "/service/" in current_url:
                logger.info("✅ 已通过 Cloudflare 验证，进入目标页面")
            else:
                logger.warning(f"可能仍在验证中，当前URL: {current_url}")
                # 截图调试
                try:
                    debug_filename = f"img/cf_debug_{int(time.time())}.png"
                    page.screenshot(path=debug_filename)
                    logger.info(f"已保存调试截图: {debug_filename}")
                except:
                    pass
                
        except Exception as e:
            logger.warning(f"处理 Cloudflare 验证时出错: {str(e)}")
    
    def _take_debug_screenshot(self, page: Page, server_name: str):
        """截图保存失败状态用于调试"""
        try:
            # 确保 img 文件夹存在
            os.makedirs('img', exist_ok=True)
            
            # 生成调试截图文件名
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            filename = f"img/debug_failed_{server_name}_{timestamp}.png"
            
            # 截图当前状态
            page.screenshot(path=filename)
            logger.info(f"🔍 调试截图已保存: {filename}")
            
            # 同时记录当前URL用于调试
            current_url = page.url
            logger.info(f"🔍 当前页面URL: {current_url}")
            
        except Exception as e:
            logger.error(f"调试截图保存失败: {str(e)}")
    
    def login(self, headless: bool = True) -> bool:
        """使用 Cookie 自动登录"""
        try:
            with sync_playwright() as p:
                # 启动浏览器
                browser = p.chromium.launch(
                    headless=headless,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled'
                    ]
                )
                
                # 创建上下文
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                
                # 创建页面
                page = context.new_page()
                
                # 设置 Cookie
                logger.info("正在设置 Cookie...")
                success = self._set_cookies(page)
                
                if success:
                    # 访问第一个服务器进行验证
                    first_server = self.servers[0]
                    server_url = first_server['url']
                    server_name = first_server.get('name', f"服务器{first_server['id']}")
                    
                    logger.info(f"正在使用 Cookie 访问服务器: {server_name} ({server_url})")
                    
                    try:
                        page.goto(server_url, wait_until='networkidle', timeout=60000)
                        logger.info("页面加载完成")
                        
                        # 检查是否被重定向到登录页面
                        current_url = page.url
                        logger.info(f"当前页面URL: {current_url}")
                        
                        if "/auth/login" in current_url:
                            logger.error("❌ Cookie 登录失败或会话已过期，页面被重定向到登录页面")
                            page.context.clear_cookies()
                            return False
                        else:
                            logger.info("✅ Cookie 登录成功！")
                            
                            # 截图保存
                            self._take_screenshot(page, server_name)
                            return True
                            
                    except Exception as e:
                        logger.error(f"访问页面时发生错误: {str(e)}")
                        return False
                else:
                    logger.error("Cookie 设置失败")
                    return False
                    
        except Exception as e:
            logger.error(f"登录过程中发生错误: {str(e)}")
            return False
        finally:
            try:
                browser.close()
            except:
                pass
    
    def _set_cookies(self, page: Page) -> bool:
        """设置登录 Cookie"""
        try:
            # 创建 Cookie 对象，属性已预定义
            # 设置过期时间为当前时间 + 1年，实现自动续期
            cookie = {
                "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                "value": self.cookie_value,
                "domain": "dash.hidencloud.com",
                "path": "/",
                "expires": int(time.time()) + 3600 * 24 * 365,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax"
            }
            
            # 设置 Cookie
            logger.info("正在设置登录 Cookie...")
            page.context.add_cookies([cookie])
            logger.info("Cookie 设置成功！")
            return True
            
        except Exception as e:
            logger.error(f"设置 Cookie 时出错: {str(e)}")
            return False
    
    
def main():
    """主函数"""
    try:
        logger.info("开始执行自动登录脚本...")
        
        # 创建登录实例
        login_client = HidenCloudLogin()
        
        # 使用 Cookie 登录（GitHub Actions 环境中使用无头模式）
        is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
        headless = is_github_actions or os.getenv('HEADLESS', 'true').lower() == 'true'
        success = login_client.login(headless=headless)
        
        if success:
            logger.info("自动登录脚本执行成功！")
            sys.exit(0)
        else:
            logger.error("自动登录脚本执行失败！")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"脚本执行过程中发生错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
