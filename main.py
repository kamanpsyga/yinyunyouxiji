#!/usr/bin/env python3
"""
HidenCloud 自动登录脚本
"""

import os
import sys
import time
import logging
from playwright.sync_api import sync_playwright, Page

# =====================================================================
#                          日志配置
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


# =====================================================================
#                       HidenCloud 自动登录类
# =====================================================================
class HidenCloudLogin:
    """HidenCloud 自动登录主类"""
    
    def __init__(self):
        """【步骤1】初始化配置"""
        # 基础网站配置
        self.base_url = "https://dash.hidencloud.com"
        self.login_url = "https://dash.hidencloud.com/auth/login"
        
        # 【步骤1.1】加载并解析服务器配置
        self._load_server_config()
        
        # 【步骤1.2】加载并解析登录凭据
        self._load_credentials()
        
        # 【步骤1.3】验证配置完整性
        self._validate_config()
    
    # =================================================================
    #                       配置加载方法组
    # =================================================================
    
    def _load_server_config(self):
        """【配置加载1】获取服务器配置"""
        try:
            # 获取环境变量中的服务器配置JSON
            server_json = os.getenv('HIDENCLOUD_SERVERS')
            if not server_json:
                raise ValueError("未设置环境变量 HIDENCLOUD_SERVERS")
            
            # 解析JSON配置
            import json
            servers = json.loads(server_json)
            if not servers:
                raise ValueError("服务器配置为空")
            
            # 提取第一个服务器的配置信息
            server = servers[0]
            self.server_url = server['url']
            self.server_name = server.get('name', f"服务器{server['id']}")
            
            logger.info(f"✅ 服务器配置加载成功: {self.server_name} ({self.server_url})")
            
        except json.JSONDecodeError as e:
            raise ValueError(f"❌ 服务器配置JSON解析失败: {str(e)}")
        except Exception as e:
            raise ValueError(f"❌ 加载服务器配置失败: {str(e)}")
    
    def _load_credentials(self):
        """【配置加载2】加载登录凭据"""
        # 方式1：Cookie 登录凭据（优先级较高，速度快）
        self.cookie_value = os.getenv('REMEMBER_WEB_COOKIE')
        if self.cookie_value:
            logger.info("✅ Cookie 登录凭据已加载")
        else:
            logger.warning("⚠️  未找到 Cookie 登录凭据")
        
        # 方式2：邮箱密码登录凭据（备用方案，兼容性好）
        account_info = os.getenv('HIDENCLOUD_ACCOUNT')
        if account_info:
            try:
                self.email, self.password = account_info.split(':')
                logger.info("✅ 邮箱密码登录凭据已加载")
            except ValueError:
                logger.error("❌ HIDENCLOUD_ACCOUNT 格式错误，应为 'email:password'")
                self.email = None
                self.password = None
        else:
            logger.warning("⚠️  未找到邮箱密码登录凭据")
            self.email = None
            self.password = None
    
    def _validate_config(self):
        """【配置加载3】验证配置完整性"""
        if not self.cookie_value and not (self.email and self.password):
            raise ValueError("❌ 必须提供 REMEMBER_WEB_COOKIE 或 HIDENCLOUD_ACCOUNT（格式：email:password）")
        
        logger.info("✅ 配置验证通过，登录凭据完整")
    
    # =================================================================
    #                       主要登录流程
    # =================================================================
    
    def login(self, headless: bool = True) -> bool:
        """【步骤2】主登录流程"""
        try:
            logger.info("🚀 开始执行登录流程...")
            
            with sync_playwright() as p:
                # 【步骤2.1】启动浏览器并配置环境
                browser = p.chromium.launch(
                    headless=headless,
                    args=[
                        '--no-sandbox',              # 沙盒模式（CI环境需要）
                        '--disable-dev-shm-usage',   # 禁用开发共享内存
                        '--disable-blink-features=AutomationControlled'  # 隐藏自动化特征
                    ]
                )
                logger.info("✅ 浏览器启动成功")
                
                # 【步骤2.2】创建浏览器上下文（模拟真实用户环境）
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                logger.info("✅ 浏览器上下文创建成功")
                
                # 【步骤2.3】创建页面实例
                page = context.new_page()
                logger.info("✅ 页面实例创建成功")
                
                # 【步骤2.4】执行智能登录策略
                logger.info("🔐 开始尝试登录...")
                
                # 策略1：优先尝试Cookie登录（速度快，成功率高）
                if self._try_cookie_login(page):
                    logger.info("🎉 Cookie登录成功完成！")
                    return True
                
                # 策略2：Cookie失败时尝试邮箱密码登录（兼容性好）
                elif self._try_password_login(page):
                    logger.info("🎉 邮箱密码登录成功完成！")
                    return True
                
                # 策略3：所有方式都失败
                else:
                    logger.error("❌ 所有登录方式均失败")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ 登录过程中发生错误: {str(e)}")
            return False
    
    # =================================================================
    #                      Cookie 登录方法组
    # =================================================================
    
    def _try_cookie_login(self, page: Page) -> bool:
        """【登录策略1】Cookie 快速登录"""
        if not self.cookie_value:
            logger.info("⏭️  未提供 Cookie，跳过 Cookie 登录")
            return False
        
        logger.info("🍪 开始尝试 Cookie 登录...")
        
        # 【Cookie登录步骤1】设置认证Cookie
        if not self._set_cookies(page):
            logger.error("❌ Cookie 设置失败")
            return False
        
        # 【Cookie登录步骤2】访问目标服务器页面
        try:
            logger.info(f"🌐 正在访问目标页面: {self.server_url}")
            page.goto(self.server_url, wait_until='networkidle', timeout=60000)
            logger.info("✅ 页面加载完成")
            
            # 【Cookie登录步骤3】验证登录状态
            if self._is_login_required(page):
                logger.warning("⚠️  Cookie 已失效，需要重新登录")
                page.context.clear_cookies()  # 清除失效Cookie
                return False
            
            # 【Cookie登录步骤4】登录成功处理
            logger.info("✅ Cookie 登录成功！")
            self._take_screenshot(page, "cookie_success")
            
            # 执行续费操作
            self._perform_renewal(page)
            return True
            
        except Exception as e:
            logger.warning(f"⚠️  Cookie 登录失败: {str(e)}")
            return False
    
    # =================================================================
    #                     邮箱密码登录方法组
    # =================================================================
    
    def _try_password_login(self, page: Page) -> bool:
        """【登录策略2】邮箱密码登录"""
        if not (self.email and self.password):
            logger.error("❌ 未提供邮箱密码，无法执行密码登录")
            return False
        
        logger.info("📧 开始尝试邮箱密码登录...")
        
        try:
            # 【密码登录步骤1】访问登录页面
            logger.info(f"🌐 正在访问登录页面: {self.login_url}")
            page.goto(self.login_url, wait_until="networkidle", timeout=60000)
            logger.info("✅ 登录页面加载完成")
            
            # 【密码登录步骤2】填写登录表单
            logger.info("📝 正在填写登录信息...")
            page.fill('input[name="email"]', self.email)
            page.fill('input[name="password"]', self.password)
            logger.info("✅ 登录信息填写完成")
            
            # 【密码登录步骤3】处理 Cloudflare 验证（如果存在）
            self._handle_cloudflare_verification(page)
            
            # 【密码登录步骤4】提交登录表单
            logger.info("🚀 正在提交登录表单...")
            page.click('button[type="submit"]:has-text("Sign in to your account")')
            logger.info("✅ 登录表单已提交，等待系统响应...")
            
            # 【密码登录步骤5】等待登录完成并跳转
            page.wait_for_url(f"{self.base_url}/dashboard", timeout=60000)
            logger.info("✅ 成功跳转到控制面板")
            
            # 【密码登录步骤6】验证登录状态
            if self._is_login_required(page):
                logger.error("❌ 登录验证失败，请检查账号密码")
                self._take_screenshot(page, "password_failed")
                return False
            
            logger.info("✅ 邮箱密码登录验证成功！")
            
            # 【密码登录步骤7】访问目标服务器页面
            logger.info(f"🌐 正在访问目标服务器: {self.server_url}")
            page.goto(self.server_url, wait_until="networkidle", timeout=60000)
            self._take_screenshot(page, "password_success")
            
            # 执行续费操作
            self._perform_renewal(page)
            return True
            
        except Exception as e:
            logger.error(f"❌ 邮箱密码登录失败: {str(e)}")
            self._take_screenshot(page, "password_failed")
            return False
    
    # =================================================================
    #                        辅助工具方法组
    # =================================================================
    
    def _set_cookies(self, page: Page) -> bool:
        """【辅助工具1】设置登录 Cookie"""
        try:
            # 构建标准的Cookie对象
            cookie = {
                "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",  # HidenCloud记住登录的Cookie名称
                "value": self.cookie_value,                                       # Cookie值
                "domain": "dash.hidencloud.com",                                  # 作用域
                "path": "/",                                                      # 路径
                "expires": int(time.time()) + 3600 * 24 * 365,                    # 有效期：1年
                "httpOnly": True,                                                 # 仅HTTP访问
                "secure": True,                                                   # 仅HTTPS传输
                "sameSite": "Lax"                                                 # 跨站策略
            }
            
            # 将Cookie添加到浏览器上下文
            page.context.add_cookies([cookie])
            logger.info("✅ Cookie 设置完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cookie 设置失败: {str(e)}")
            return False
    
    def _handle_cloudflare_verification(self, page: Page):
        """【辅助工具2】处理 Cloudflare Turnstile 验证"""
        logger.info("🔍 检查是否存在 Cloudflare 验证...")
        
        try:
            # 【验证步骤1】查找Cloudflare验证框架
            turnstile_frame = page.frame_locator('iframe[src*="challenges.cloudflare.com"]')
            checkbox = turnstile_frame.locator('input[type="checkbox"]')
            
            # 【验证步骤2】等待验证框出现并点击
            checkbox.wait_for(state="visible", timeout=30000)
            checkbox.click()
            logger.info("✅ 已点击Cloudflare验证复选框")
            
            # 【验证步骤3】等待验证完成
            page.wait_for_function(
                "() => document.querySelector('[name=\"cf-turnstile-response\"]') && document.querySelector('[name=\"cf-turnstile-response\"]').value",
                timeout=60000
            )
            logger.info("✅ Cloudflare 验证通过完成")
            
        except Exception as e:
            logger.warning(f"⚠️  Cloudflare 验证处理失败，继续尝试登录: {str(e)}")
    
    def _is_login_required(self, page: Page) -> bool:
        """【辅助工具3】检查登录状态"""
        is_login_page = "/auth/login" in page.url
        if is_login_page:
            logger.info("📍 当前在登录页面，需要执行登录")
        else:
            logger.info("📍 已登录状态，无需重复登录")
        return is_login_page
    
    def _take_screenshot(self, page: Page, status: str):
        """【辅助工具4】智能截图保存"""
        try:
            # 等待页面完全渲染
            time.sleep(3)
            
            # 生成带时间戳的文件名
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            filename = f"{status}_{self.server_name}_{timestamp}.png"
            
            # 保存全页面截图
            page.screenshot(path=filename)
            logger.info(f"📸 截图已保存: {filename}")
            
        except Exception as e:
            logger.error(f"❌ 截图保存失败: {str(e)}")

    # =================================================================
    #                        续费功能方法组
    # =================================================================
    
    def _perform_renewal(self, page: Page):
        """【续费功能】执行服务续费操作"""
        try:
            logger.info("🔄 开始执行服务续费操作...")
            
            # 【续费步骤0】记录续费前的到期时间
            self._record_due_date_before_renewal(page)
            
            # 【续费步骤1】查找并点击Renew按钮
            renew_button = page.locator('button:has-text("Renew")')
            
            # 等待按钮出现并检查是否可点击
            renew_button.wait_for(state="visible", timeout=10000)
            
            if renew_button.is_enabled():
                logger.info("🎯 找到Renew按钮，准备点击...")
                renew_button.click()
                logger.info("✅ 已点击Renew按钮")
                
                # 【续费步骤2】处理续费弹窗（可能是确认弹窗或限制弹窗）
                self._handle_renewal_dialog(page)
                
            else:
                logger.warning("⚠️  Renew按钮存在但不可点击，可能服务不需要续费")
                
        except Exception as e:
            logger.warning(f"⚠️  续费操作执行失败: {str(e)}")
            self._take_screenshot(page, "renewal_failed")
    
    def _handle_renewal_dialog(self, page: Page):
        """【续费弹窗】处理续费相关弹窗"""
        try:
            logger.info("💬 等待弹窗出现...")
            time.sleep(2)  # 等待弹窗完全加载
            
            # 检查是否是续费限制弹窗
            if self._check_renewal_restriction(page):
                return
            
            # 检查是否是续费确认弹窗
            if self._check_renewal_confirmation(page):
                return
                
            # 如果都没有检测到，说明可能有其他情况
            logger.warning("⚠️  未检测到预期的弹窗")
            self._take_screenshot(page, "unexpected_dialog")
                
        except Exception as e:
            logger.warning(f"⚠️  处理续费弹窗失败: {str(e)}")
            self._take_screenshot(page, "renewal_dialog_failed")
    
    def _check_renewal_restriction(self, page: Page) -> bool:
        """【限制检查】检查是否出现续费限制弹窗"""
        try:
            # 检查关键元素1：标题
            restriction_title = page.locator('text="Renewal Restricted"')
            
            # 检查关键元素2：限制说明
            restriction_message = page.locator('text="You can only renew your free service when there is less than 1 day left before it expires."')
            
            if restriction_title.is_visible() and restriction_message.is_visible():
                logger.warning("⚠️  检测到续费限制弹窗")
                logger.info("📋 执行结果: 未到续期时间")
                self._take_screenshot(page, "renewal_restricted")
                return True
                
        except Exception as e:
            logger.warning(f"⚠️  检查续费限制时出错: {str(e)}")
            
        return False
    
    def _check_renewal_confirmation(self, page: Page) -> bool:
        """【确认检查】检查是否出现续费确认弹窗"""
        try:
            # 检查关键元素1：标题
            confirmation_title = page.locator('text="Renew Plan"')
            
            # 检查关键元素2：续费说明
            confirmation_message = page.locator('text*="Below you can renew your service for another Week. After hitting "Renew", we will generate an invoice for you to pay."')
            
            if confirmation_title.is_visible() and confirmation_message.is_visible():
                logger.info("✅ 检测到Renew Plan确认弹窗")
                
                # 查找并点击Create Invoice按钮
                create_invoice_button = page.locator('button:has-text("Create Invoice")')
                
                if create_invoice_button.is_visible():
                    logger.info("🎯 找到Create Invoice按钮，点击确认...")
                    create_invoice_button.click()
                    logger.info("✅ Invoice创建请求已提交")
                    
                    # 等待跳转到Invoice页面并处理支付
                    self._handle_payment(page)
                    return True
                    
                else:
                    logger.warning("⚠️  未找到Create Invoice按钮")
                    self._take_screenshot(page, "renewal_dialog_error")
                    return True
                    
        except Exception as e:
            logger.warning(f"⚠️  检查续费确认时出错: {str(e)}")
            
        return False
    
    def _handle_payment(self, page: Page):
        """【支付处理】处理Invoice支付"""
        try:
            logger.info("💳 等待Invoice页面加载...")
            
            # 等待成功提示出现
            success_message = page.locator('text*="Success! Invoice has been generated successfully"')
            success_message.wait_for(state="visible", timeout=15000)
            logger.info("✅ Invoice生成成功提示已显示")
            
            # 查找并点击Pay按钮
            pay_button = page.locator('button:has-text("Pay")')
            
            if pay_button.is_visible():
                logger.info("🎯 找到Pay按钮，点击支付...")
                pay_button.click()
                logger.info("✅ 支付请求已提交")
                
                # 等待跳转回Dashboard并检查支付结果
                self._check_payment_result(page)
                
            else:
                logger.warning("⚠️  未找到Pay按钮")
                self._take_screenshot(page, "payment_button_error")
                
        except Exception as e:
            logger.warning(f"⚠️  处理支付失败: {str(e)}")
            self._take_screenshot(page, "payment_failed")
    
    def _check_payment_result(self, page: Page):
        """【支付结果】检查支付完成状态"""
        try:
            logger.info("🔍 等待支付处理完成...")
            
            # 等待跳转回Dashboard页面
            page.wait_for_url("**/dashboard", timeout=15000)
            logger.info("✅ 已跳转回Dashboard页面")
            
            # 检查支付成功提示
            payment_success = page.locator('text*="Success! Your payment has been completed!"')
            payment_success.wait_for(state="visible", timeout=10000)
            
            logger.info("🎉 支付成功！续费操作已完成")
            logger.info("✅ 显示成功提示: 'Success! Your payment has been completed!'")
            
            # 保存Dashboard页面的成功截图
            self._take_screenshot(page, "renewal_payment_success")
            
            # 跳转回服务管理页面记录新的到期时间
            logger.info("🔄 跳转回服务管理页面记录新到期时间...")
            page.goto(self.server_url, wait_until="networkidle", timeout=30000)
            logger.info("✅ 已跳转回服务管理页面")
            
            # 记录续费后的新到期时间
            self._record_due_date_after_renewal(page)
            
        except Exception as e:
            logger.warning(f"⚠️  支付结果检查失败: {str(e)}")
            logger.info("📋 支付可能已完成，请手动确认最终状态")
            self._take_screenshot(page, "payment_result_unknown")
    
    # =================================================================
    #                        到期时间记录方法组
    # =================================================================
    
    def _record_due_date_before_renewal(self, page: Page):
        """【时间记录1】记录续费前的到期时间"""
        try:
            logger.info("📅 正在记录续费前的到期时间...")
            
            # 方法1：通过Due date标签定位
            logger.info("🔍 [调试] 尝试方法1：通过Due date标签定位")
            try:
                due_date_label = page.locator('text="Due date"')
                logger.info(f"🔍 [调试] Due date标签是否可见: {due_date_label.is_visible()}")
                
                if due_date_label.is_visible():
                    # 查找Due date后面的日期文本（格式：DD MMM YYYY）
                    parent_container = due_date_label.locator('..')
                    logger.info("🔍 [调试] 已找到Due date父容器")
                    
                    # 使用正则匹配日期格式
                    date_text = parent_container.locator('text=/\\d{1,2}\\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+\\d{4}/').first
                    logger.info(f"🔍 [调试] 日期文本是否可见: {date_text.is_visible()}")
                    
                    if date_text.is_visible():
                        due_date = date_text.text_content().strip()
                        logger.info(f"✅ [调试] 方法1成功获取到期时间: {due_date}")
                        return due_date
                    else:
                        logger.warning("⚠️ [调试] 方法1：在父容器中未找到日期格式文本")
                else:
                    logger.warning("⚠️ [调试] 方法1：未找到Due date标签")
            except Exception as e:
                logger.warning(f"⚠️ [调试] 方法1异常: {str(e)}")
            
            # 方法2：直接查找日期格式文本
            logger.info("🔍 [调试] 尝试方法2：直接查找日期格式文本")
            try:
                # 查找符合日期格式的文本（DD MMM YYYY）
                date_elements = page.locator('text=/\\d{1,2}\\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+\\d{4}/')
                element_count = date_elements.count()
                logger.info(f"🔍 [调试] 找到的日期格式元素数量: {element_count}")
                
                if element_count > 0:
                    due_date = date_elements.first.text_content().strip()
                    logger.info(f"✅ [调试] 方法2成功获取到期时间: {due_date}")
                    return due_date
                else:
                    logger.warning("⚠️ [调试] 方法2：未找到任何日期格式文本")
            except Exception as e:
                logger.warning(f"⚠️ [调试] 方法2异常: {str(e)}")
                
            logger.warning("⚠️  无法找到续费前的到期时间")
            return None
                
        except Exception as e:
            logger.warning(f"⚠️  记录续费前到期时间失败: {str(e)}")
            return None
    
    def _record_due_date_after_renewal(self, page: Page):
        """【时间记录2】记录续费后的新到期时间"""
        try:
            logger.info("📅 正在记录续费后的到期时间...")
            
            # 等待页面加载完成
            time.sleep(2)
            
            # 使用与续费前相同的方法查找到期时间
            # 方法1：通过Due date标签定位
            logger.info("🔍 [调试] 续费后-尝试方法1：通过Due date标签定位")
            try:
                due_date_label = page.locator('text="Due date"')
                logger.info(f"🔍 [调试] 续费后-Due date标签是否可见: {due_date_label.is_visible()}")
                
                if due_date_label.is_visible():
                    # 查找Due date后面的日期文本（格式：DD MMM YYYY）
                    parent_container = due_date_label.locator('..')
                    logger.info("🔍 [调试] 续费后-已找到Due date父容器")
                    
                    # 使用正则匹配日期格式
                    date_text = parent_container.locator('text=/\\d{1,2}\\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+\\d{4}/').first
                    logger.info(f"🔍 [调试] 续费后-日期文本是否可见: {date_text.is_visible()}")
                    
                    if date_text.is_visible():
                        due_date = date_text.text_content().strip()
                        logger.info(f"✅ [调试] 续费后-方法1成功获取到期时间: {due_date}")
                        return due_date
                    else:
                        logger.warning("⚠️ [调试] 续费后-方法1：在父容器中未找到日期格式文本")
                else:
                    logger.warning("⚠️ [调试] 续费后-方法1：未找到Due date标签")
            except Exception as e:
                logger.warning(f"⚠️ [调试] 续费后-方法1异常: {str(e)}")
            
            # 方法2：直接查找日期格式文本
            logger.info("🔍 [调试] 续费后-尝试方法2：直接查找日期格式文本")
            try:
                # 查找符合日期格式的文本（DD MMM YYYY）
                date_elements = page.locator('text=/\\d{1,2}\\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+\\d{4}/')
                element_count = date_elements.count()
                logger.info(f"🔍 [调试] 续费后-找到的日期格式元素数量: {element_count}")
                
                if element_count > 0:
                    # 通常最新的日期会是续费后的日期
                    due_date = date_elements.first.text_content().strip()
                    logger.info(f"✅ [调试] 续费后-方法2成功获取到期时间: {due_date}")
                    return due_date
                else:
                    logger.warning("⚠️ [调试] 续费后-方法2：未找到任何日期格式文本")
            except Exception as e:
                logger.warning(f"⚠️ [调试] 续费后-方法2异常: {str(e)}")
                
            logger.warning("⚠️  无法找到续费后的到期时间")
            return None
                
        except Exception as e:
            logger.warning(f"⚠️  记录续费后到期时间失败: {str(e)}")
            return None


# =====================================================================
#                          主程序入口
# =====================================================================

def main():
    """【步骤3】主程序执行流程"""
    try:
        logger.info("🚀 开始执行 HidenCloud 自动登录脚本...")
        
        # 【主程序步骤1】创建登录客户端实例
        logger.info("📋 正在初始化登录客户端...")
        login_client = HidenCloudLogin()
        logger.info("✅ 登录客户端初始化完成")
        
        # 【主程序步骤2】确定浏览器运行模式
        is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
        headless = is_github_actions or os.getenv('HEADLESS', 'true').lower() == 'true'
        
        if headless:
            logger.info("👻 使用无头模式运行（适合CI/CD环境）")
        else:
            logger.info("🖥️  使用有界面模式运行（适合本地调试）")
        
        # 【主程序步骤3】执行智能登录流程
        logger.info("🔐 开始执行智能登录流程...")
        success = login_client.login(headless=headless)
        
        # 【主程序步骤4】处理执行结果
        if success:
            logger.info("🎉 自动登录脚本执行成功！")
            logger.info("📊 任务完成，系统即将正常退出")
            sys.exit(0)
        else:
            logger.error("❌ 自动登录脚本执行失败！")
            logger.error("🔧 请检查配置信息和网络连接")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"💥 脚本执行过程中发生严重错误: {str(e)}")
        logger.error("🔧 请检查环境配置和依赖安装")
        sys.exit(1)


# =====================================================================
#                          程序启动点
# =====================================================================

if __name__ == "__main__":
    main()
