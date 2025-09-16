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
            
            # 等待页面网络空闲状态
            page.wait_for_load_state('networkidle', timeout=30000)
            
            # 再等待几秒确保页面渲染完成
            time.sleep(5)
            
            # 生成截图文件名
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            filename = f"img/login_success_{server_name}_{timestamp}.png"
            
            # 截图
            page.screenshot(path=filename)
            logger.info(f"📸 截图已保存: {filename}")
            
        except Exception as e:
            logger.error(f"截图保存失败: {str(e)}")
    
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
                    
                    logger.info(f"正在访问服务器: {server_name} ({server_url})")
                    
                    # 增加超时时间，因为可能有 CF 验证
                    try:
                        page.goto(server_url, wait_until='networkidle', timeout=60000)  # 60秒超时
                        logger.info("页面加载完成")
                    except Exception as e:
                        logger.warning(f"页面加载超时，尝试继续: {str(e)}")
                        # 即使超时也尝试继续，可能页面已经部分加载
                    
                    # 等待 CF 验证完成
                    logger.info("等待 Cloudflare 安全验证...")
                    time.sleep(15)  # 给更多时间让 CF 验证完成
                    
                    # 验证是否成功访问
                    if self._verify_access(page, server_url):
                        logger.info(f"自动登录成功！已成功访问 {server_name}")
                        
                        # 截图保存
                        self._take_screenshot(page, server_name)
                        
                        return True
                    else:
                        logger.error(f"登录失败：无法访问 {server_name}")
                        # 截图失败状态用于调试
                        self._take_debug_screenshot(page, server_name)
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
            # 先访问基础域名以设置 Cookie
            logger.info(f"正在访问基础域名: {self.base_url}")
            page.goto(self.base_url, wait_until='networkidle')
            
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
    
    def _verify_access(self, page: Page, target_url: str) -> bool:
        """验证页面访问是否成功"""
        try:
            current_url = page.url
            logger.info(f"当前页面URL: {current_url}")
            
            # 检查是否被重定向到登录页面
            if "/auth/login" in current_url:
                logger.error("页面被重定向到登录页面，Cookie 已失效")
                return False
            
            logger.info("✅ Cookie 登录验证成功")
            return True
            
        except Exception as e:
            logger.error(f"验证页面访问时出错: {str(e)}")
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
