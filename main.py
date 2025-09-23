#!/usr/bin/env python3
"""
HidenCloud 自动登录和续费脚本
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
    """HidenCloud 自动登录和续费主类"""
    
    def __init__(self):
        """初始化配置和运行结果收集器"""
        # 基础网站配置
        self.base_url = "https://dash.hidencloud.com"
        self.login_url = "https://dash.hidencloud.com/auth/login"
        
        # 加载配置
        self._load_server_config()
        self._load_credentials()
        self._validate_config()
        
        # 初始化运行结果收集器
        self.run_results = {
            'server_id': f"{self.server_name}({self.server_id})",
            'renewal_status': 'Unknown',
            'remaining_days': None,
            'old_due_date': None,
            'new_due_date': None,
            'start_time': time.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    # =================================================================
    #                       1. 配置加载模块
    # =================================================================
    
    def _load_server_config(self):
        """加载服务器配置"""
        try:
            server_json = os.getenv('HIDENCLOUD_SERVERS')
            if not server_json:
                raise ValueError("未设置环境变量 HIDENCLOUD_SERVERS")
            
            import json
            servers = json.loads(server_json)
            if not servers:
                raise ValueError("服务器配置为空")
            
            server = servers[0]
            self.server_url = server['url']
            self.server_id = server['id']
            self.server_name = server.get('name', f"服务器{server['id']}")
            
            logger.info(f"✅ 服务器配置加载成功: {self.server_name} ({self.server_url})")
            
        except json.JSONDecodeError as e:
            raise ValueError(f"❌ 服务器配置JSON解析失败: {str(e)}")
        except Exception as e:
            raise ValueError(f"❌ 加载服务器配置失败: {str(e)}")
    
    def _load_credentials(self):
        """加载登录凭据"""
        # Cookie 登录凭据（优先）
        self.cookie_value = os.getenv('REMEMBER_WEB_COOKIE')
        if self.cookie_value:
            logger.info("✅ Cookie 登录凭据已加载")
        else:
            logger.warning("⚠️  未找到 Cookie 登录凭据")
        
        # 邮箱密码登录凭据（备用）
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
        """验证配置完整性"""
        if not self.cookie_value and not (self.email and self.password):
            raise ValueError("❌ 必须提供 REMEMBER_WEB_COOKIE 或 HIDENCLOUD_ACCOUNT（格式：email:password）")
        
        logger.info("✅ 配置验证通过，登录凭据完整")
    
    # =================================================================
    #                       2. 主登录流程模块
    # =================================================================
    
    def login(self, headless: bool = True) -> bool:
        """主登录流程入口"""
        try:
            logger.info("🚀 开始执行登录流程...")
            
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
                logger.info("✅ 浏览器启动成功")
                
                # 创建浏览器上下文
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                logger.info("✅ 浏览器上下文创建成功")
                
                # 创建页面实例
                page = context.new_page()
                logger.info("✅ 页面实例创建成功")
                
                # 执行智能登录策略
                logger.info("🔐 开始尝试登录...")
                
                # 策略1：优先尝试Cookie登录
                if self._try_cookie_login(page):
                    logger.info("🎉 Cookie登录成功完成！")
                    return True
                
                # 策略2：Cookie失败时尝试邮箱密码登录
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
    #                       3. Cookie登录模块
    # =================================================================
    
    def _try_cookie_login(self, page: Page) -> bool:
        """Cookie 快速登录"""
        if not self.cookie_value:
            logger.info("⏭️  未提供 Cookie，跳过 Cookie 登录")
            return False
        
        logger.info("🍪 开始尝试 Cookie 登录...")
        
        # 设置认证Cookie
        if not self._set_cookies(page):
            logger.error("❌ Cookie 设置失败")
            return False
        
        # 访问目标服务器页面
        try:
            logger.info(f"🌐 正在访问目标页面: {self.server_url}")
            page.goto(self.server_url, wait_until='networkidle', timeout=60000)
            logger.info("✅ 页面加载完成")
            
            # 验证登录状态
            if self._is_login_required(page):
                logger.warning("⚠️  Cookie 已失效，需要重新登录")
                page.context.clear_cookies()
                return False
            
            # 登录成功处理
            logger.info("✅ Cookie 登录成功！")
            self._take_screenshot(page, "cookie_success")
            
            # 执行续费操作
            self._perform_renewal(page)
            return True
            
        except Exception as e:
            logger.warning(f"⚠️  Cookie 登录失败: {str(e)}")
            return False
    
    def _set_cookies(self, page: Page) -> bool:
        """设置登录 Cookie"""
        try:
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
            
            page.context.add_cookies([cookie])
            logger.info("✅ Cookie 设置完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cookie 设置失败: {str(e)}")
            return False
    
    # =================================================================
    #                       4. 邮箱密码登录模块
    # =================================================================
    
    def _try_password_login(self, page: Page) -> bool:
        """邮箱密码登录"""
        if not (self.email and self.password):
            logger.error("❌ 未提供邮箱密码，无法执行密码登录")
            return False
        
        logger.info("📧 开始尝试邮箱密码登录...")
        
        try:
            # 访问登录页面
            logger.info(f"🌐 正在访问登录页面: {self.login_url}")
            page.goto(self.login_url, wait_until="networkidle", timeout=60000)
            logger.info("✅ 登录页面加载完成")
            
            # 填写登录表单
            logger.info("📝 正在填写登录信息...")
            page.fill('input[name="email"]', self.email)
            page.fill('input[name="password"]', self.password)
            logger.info("✅ 登录信息填写完成")
            
            # 处理 Cloudflare 验证
            self._handle_cloudflare_verification(page)
            
            # 提交登录表单
            logger.info("🚀 正在提交登录表单...")
            page.click('button[type="submit"]:has-text("Sign in to your account")')
            logger.info("✅ 登录表单已提交，等待系统响应...")
            
            # 等待登录完成并跳转
            page.wait_for_url(f"{self.base_url}/dashboard", timeout=60000)
            logger.info("✅ 成功跳转到控制面板")
            
            # 验证登录状态
            if self._is_login_required(page):
                logger.error("❌ 登录验证失败，请检查账号密码")
                self._take_screenshot(page, "password_failed")
                return False
            
            logger.info("✅ 邮箱密码登录验证成功！")
            
            # 访问目标服务器页面
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
    
    def _handle_cloudflare_verification(self, page: Page):
        """处理 Cloudflare Turnstile 验证"""
        logger.info("🔍 检查是否存在 Cloudflare 验证...")
        
        try:
            turnstile_frame = page.frame_locator('iframe[src*="challenges.cloudflare.com"]')
            checkbox = turnstile_frame.locator('input[type="checkbox"]')
            
            checkbox.wait_for(state="visible", timeout=30000)
            checkbox.click()
            logger.info("✅ 已点击Cloudflare验证复选框")
            
            page.wait_for_function(
                "() => document.querySelector('[name=\"cf-turnstile-response\"]') && document.querySelector('[name=\"cf-turnstile-response\"]').value",
                timeout=60000
            )
            logger.info("✅ Cloudflare 验证通过完成")
            
        except Exception as e:
            logger.warning(f"⚠️  Cloudflare 验证处理失败，继续尝试登录: {str(e)}")
    
    # =================================================================
    #                       5. 续费功能模块
    # =================================================================
    
    def _perform_renewal(self, page: Page):
        """执行服务续费操作"""
        try:
            logger.info("🔄 开始执行服务续费操作...")
            
            # 步骤1：记录续费前的到期时间
            self._record_due_date(page, "续费前")
            
            # 步骤2：查找并点击Renew按钮
            renew_button = page.locator('button:has-text("Renew")')
            renew_button.wait_for(state="visible", timeout=10000)
            
            if renew_button.is_enabled():
                logger.info("🎯 找到Renew按钮，准备点击...")
                renew_button.click()
                logger.info("✅ 已点击Renew按钮")
                
                # 步骤3：处理续费弹窗
                self._handle_renewal_dialog(page)
                
            else:
                logger.warning("⚠️  Renew按钮存在但不可点击，可能服务不需要续费")
                
        except Exception as e:
            logger.warning(f"⚠️  续费操作执行失败: {str(e)}")
            self._take_screenshot(page, "renewal_failed")
    
    def _handle_renewal_dialog(self, page: Page):
        """处理续费相关弹窗"""
        try:
            logger.info("💬 等待弹窗出现...")
            time.sleep(2)
            
            # 检查续费限制弹窗
            if self._check_renewal_restriction(page):
                logger.info("📋 检测到续费限制弹窗，执行结果: 未到续期时间")
                return
            
            # 检查续费确认弹窗
            if self._check_renewal_confirmation(page):
                logger.info("📋 检测到续费确认弹窗，开始执行续费流程")
                return
                
            # 未检测到预期弹窗
            logger.warning("⚠️  未检测到预期的弹窗")
            self._take_screenshot(page, "unexpected_dialog")
                
        except Exception as e:
            logger.warning(f"⚠️  处理续费弹窗失败: {str(e)}")
            self._take_screenshot(page, "renewal_dialog_failed")
    
    def _check_renewal_restriction(self, page: Page) -> bool:
        """检查续费限制弹窗"""
        try:
            # 检测弹窗标题
            restriction_title = page.locator('text="Renewal Restricted"')
            
            # 使用更精确的选择器检测限制说明（只选择p标签中的文字）
            restriction_message = page.locator('p:has-text("You can only renew your free service when there is less than 1 day left before it expires")')
            
            if restriction_title.is_visible() and restriction_message.is_visible():
                # 获取完整的限制说明文字用于日志记录
                logger.info("🔍 检测到弹窗标题: 'Renewal Restricted'")
                try:
                    full_message = restriction_message.text_content().strip()
                    logger.info(f"🔍 获取到完整限制说明文字: '{full_message}'")
                    
                    # 提取剩余天数
                    remaining_days = self._extract_remaining_days(full_message)
                    if remaining_days:
                        self.run_results['remaining_days'] = remaining_days
                        logger.info(f"🔍 提取到剩余天数: {remaining_days}天")
                    
                except Exception as e:
                    logger.warning(f"⚠️  获取完整限制说明失败: {str(e)}")
                    logger.info("🔍 检测到续费限制说明（无法获取完整内容）")
                
                # 更新续费状态
                self.run_results['renewal_status'] = 'Unexpired'
                
                logger.info("📋 确认为续费限制弹窗")
                self._take_screenshot(page, "renewal_restricted")
                return True
                
        except Exception as e:
            logger.warning(f"⚠️  检查续费限制时出错: {str(e)}")
            
        return False
    
    def _check_renewal_confirmation(self, page: Page) -> bool:
        """检查续费确认弹窗并执行续费流程"""
        try:
            confirmation_title = page.locator('text="Renew Plan"')
            confirmation_message = page.locator('text="Below you can renew your service for another Week. After hitting "Renew", we will generate an invoice for you to pay."')
            
            if confirmation_title.is_visible() and confirmation_message.is_visible():
                logger.info("🔍 检测到弹窗标题: 'Renew Plan'")
                logger.info('🔍 检测到续费说明: "Below you can renew your service for another Week. After hitting "Renew", we will generate an invoice for you to pay."')
                logger.info("📋 确认为续费确认弹窗")
                
                # 点击Create Invoice按钮
                create_invoice_button = page.locator('button:has-text("Create Invoice")')
                
                if create_invoice_button.is_visible():
                    logger.info("🎯 找到Create Invoice按钮，点击确认...")
                    create_invoice_button.click()
                    logger.info("✅ Invoice创建请求已提交")
                    
                    # 处理Invoice页面和支付
                    self._handle_invoice_and_payment(page)
                    return True
                    
                else:
                    logger.warning("⚠️  未找到Create Invoice按钮")
                    self._take_screenshot(page, "renewal_dialog_error")
                    return True
                    
        except Exception as e:
            logger.warning(f"⚠️  检查续费确认时出错: {str(e)}")
            
        return False
    
    def _handle_invoice_and_payment(self, page: Page):
        """处理Invoice页面和支付流程"""
        try:
            # 等待Invoice页面加载
            logger.info("💳 等待Invoice页面加载...")
            time.sleep(10)
            
            # 验证Invoice页面 - 检查URL和文字提示
            current_url = page.url
            logger.info(f"🔍 当前页面URL: {current_url}")
            
            # 检查URL是否匹配Invoice页面模式
            is_invoice_url = "/payment/invoice/" in current_url
            
            # 检查分离的文字提示
            success_text = page.locator('text="Success!"')
            invoice_text = page.locator('text="Invoice has been generated successfully"')
            # 使用精确匹配避免匹配到多个按钮 (Pay 和 Pay Now)
            pay_button = page.get_by_role("button", name="Pay", exact=True)
            
            if is_invoice_url and success_text.is_visible() and invoice_text.is_visible() and pay_button.is_visible():
                logger.info("🔍 URL匹配: Invoice页面")
                logger.info("🔍 检测到成功提示: 'Success!'")
                logger.info("🔍 检测到Invoice提示: 'Invoice has been generated successfully'")
                logger.info("🔍 检测到Pay按钮")
                logger.info("📋 确认为Invoice页面，开始支付流程")
                
                # 点击Pay按钮
                logger.info("🎯 点击Pay按钮...")
                pay_button.click()
                logger.info("✅ 支付请求已提交")
                
                # 等待支付处理
                logger.info("⏳ 等待支付处理...")
                time.sleep(5)
                
                # 检查支付结果
                self._check_payment_result(page)
                
            else:
                logger.warning("⚠️  无法确认Invoice页面")
                logger.info(f"🔍 URL匹配: {is_invoice_url}")
                logger.info(f"🔍 Success文字: {success_text.is_visible()}")
                logger.info(f"🔍 Invoice文字: {invoice_text.is_visible()}")
                logger.info(f"🔍 Pay按钮: {pay_button.is_visible()}")
                self._take_screenshot(page, "invoice_page_error")
                
        except Exception as e:
            logger.warning(f"⚠️  处理Invoice和支付失败: {str(e)}")
            self._take_screenshot(page, "invoice_payment_failed")
    
    def _check_payment_result(self, page: Page):
        """检查支付完成状态"""
        try:
            logger.info("🔍 等待支付处理完成...")
            
            # 等待跳转回Dashboard页面
            page.wait_for_url("**/dashboard", timeout=15000)
            logger.info("✅ 已跳转回Dashboard页面")
            
            # 检查支付成功提示文字（已跳转到Dashboard说明支付基本成功）
            try:
                payment_success_detected = self._detect_payment_success(page)
                
                if payment_success_detected:
                    logger.info("🎉 支付成功！续费操作已完成")
                    self._take_screenshot(page, "renewal_payment_success")
                else:
                    logger.info("🔍 未检测到明确的支付成功提示，但已跳转回Dashboard")
                    logger.info("📋 基于页面跳转判断支付可能已完成")
                    self._take_screenshot(page, "payment_inferred_success")
                    
            except Exception as detect_error:
                logger.warning(f"⚠️  检测支付成功提示失败: {str(detect_error)}")
                logger.info("📋 基于页面跳转判断支付可能已完成")
                self._take_screenshot(page, "payment_detection_failed")
            
            # 无论是否检测到提示文字，都继续执行后续步骤
            # 因为已经跳转到Dashboard说明支付基本成功
            self.run_results['renewal_status'] = 'Success'
            
            # 跳转回服务管理页面记录新的到期时间
            logger.info("🔄 跳转回服务管理页面记录新到期时间...")
            page.goto(self.server_url, wait_until="networkidle", timeout=30000)
            logger.info("✅ 已跳转回服务管理页面")
            
            # 记录续费后的新到期时间
            self._record_due_date(page, "续费后")
            
        except Exception as e:
            logger.warning(f"⚠️  支付结果检查失败: {str(e)}")
            logger.info("📋 支付可能已完成，请手动确认最终状态")
            self._take_screenshot(page, "payment_result_unknown")
    
    def _detect_payment_success(self, page: Page) -> bool:
        """检测支付成功提示文字（URL跳转已在上层确认）"""
        try:
            logger.info("🔍 检测支付成功提示文字...")
            
            # 检查分离的支付成功提示文字
            success_text = page.locator('text="Success!"')
            payment_text = page.locator('text="Your payment has been completed!"')
            
            try:
                # 等待两个文本都出现
                success_text.wait_for(state="visible", timeout=5000)
                payment_text.wait_for(state="visible", timeout=5000)
                
                logger.info("🔍 检测到成功提示: 'Success!'")
                logger.info("🔍 检测到支付提示: 'Your payment has been completed!'")
                return True
                
            except:
                logger.info("⚠️  未检测到支付成功提示文字")
                return False
            
        except Exception as e:
            logger.warning(f"⚠️  检测支付成功指示器失败: {str(e)}")
            return False
    
    # =================================================================
    #                       6. 时间记录模块
    # =================================================================
    
    def _record_due_date(self, page: Page, stage: str):
        """记录到期时间"""
        try:
            logger.info(f"📅 正在记录{stage}的到期时间...")
            
            # 续费后等待页面加载
            if stage == "续费后":
                time.sleep(2)
            
            # 通过Due date标签定位日期
            try:
                due_date_label = page.locator('text="Due date"')
                if due_date_label.is_visible():
                    parent_container = due_date_label.locator('..')
                    date_text = parent_container.locator('text=/\\d{1,2}\\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+\\d{4}/').first
                    if date_text.is_visible():
                        due_date_raw = date_text.text_content().strip()
                        logger.info(f"📋 {stage}原始时间: {due_date_raw}")
                        
                        # 转换日期格式
                        due_date_formatted = self._convert_date_format(due_date_raw)
                        
                        # 更新运行结果
                        if stage == "续费前":
                            self.run_results['old_due_date'] = due_date_formatted
                        elif stage == "续费后":
                            self.run_results['new_due_date'] = due_date_formatted
                            
                        return due_date_formatted
            except Exception as e:
                logger.warning(f"⚠️  获取{stage}到期时间失败: {str(e)}")
                
            logger.warning(f"⚠️  无法找到{stage}的到期时间")
            return None
                
        except Exception as e:
            logger.warning(f"⚠️  记录{stage}到期时间失败: {str(e)}")
            return None
    
    def _convert_date_format(self, date_str: str) -> str:
        """将网页日期格式转换为标准格式"""
        try:
            # 月份映射表
            month_map = {
                'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
            }
            
            # 解析日期格式：24 Sep 2025 -> 2025-09-24
            parts = date_str.strip().split()
            if len(parts) == 3:
                day = parts[0].zfill(2)
                month = month_map.get(parts[1], '00')
                year = parts[2]
                
                converted_date = f"{year}-{month}-{day}"
                logger.info(f"📅 日期格式转换: {date_str} -> {converted_date}")
                return converted_date
            else:
                logger.warning(f"⚠️  日期格式不符合预期: {date_str}")
                return date_str
                
        except Exception as e:
            logger.warning(f"⚠️  日期格式转换失败: {str(e)}")
            return date_str
    
    # =================================================================
    #                       7. 报告生成模块
    # =================================================================
    
    def generate_readme(self):
        """生成README.md运行报告"""
        try:
            logger.info("📝 正在生成README.md文件...")
            
            # 获取当前时间
            current_time = time.strftime('%Y-%m-%d %H:%M:%S')
            
            # 根据续费状态设置图标和状态文本
            if self.run_results['renewal_status'] == 'Success':
                status_icon = '✅'
                status_text = 'Success'
            elif self.run_results['renewal_status'] == 'Unexpired':
                status_icon = 'ℹ️'
                if self.run_results['remaining_days']:
                    status_text = f'Unexpired({self.run_results["remaining_days"]}天)'
                else:
                    status_text = 'Unexpired'
            else:
                status_icon = '❌'
                status_text = 'Failed'
            
            # 构建README内容
            readme_content = f"""**最后运行时间**: `{current_time}`

**运行结果**: <br>
🖥️服务器ID：`{self.run_results['server_id']}`<br>
📊续期结果：{status_icon}{status_text}<br>
🕛️旧到期时间: `{self.run_results['old_due_date'] or 'N/A'}`<br>"""
            
            # 续费成功时添加新到期时间
            if self.run_results['renewal_status'] == 'Success' and self.run_results['new_due_date']:
                readme_content += f"🕡️新到期时间：`{self.run_results['new_due_date']}`<br>\n"
            
            readme_content += "\n"
            
            # 写入README.md文件
            with open('README.md', 'w', encoding='utf-8') as f:
                f.write(readme_content)
            
            logger.info("✅ README.md文件生成成功")
            
        except Exception as e:
            logger.warning(f"⚠️  生成README.md失败: {str(e)}")
    
    # =================================================================
    #                       8. 辅助工具模块
    # =================================================================
    
    def _extract_remaining_days(self, message: str) -> int:
        """从限制说明中提取剩余天数"""
        try:
            import re
            # 使用正则表达式匹配 "expires in X days" 中的数字
            pattern = r'expires in (\d+) days?'
            match = re.search(pattern, message, re.IGNORECASE)
            
            if match:
                days = int(match.group(1))
                return days
            else:
                logger.warning("⚠️  未能从限制说明中提取剩余天数")
                return None
                
        except Exception as e:
            logger.warning(f"⚠️  提取剩余天数失败: {str(e)}")
            return None
    
    def _is_login_required(self, page: Page) -> bool:
        """检查是否需要登录"""
        is_login_page = "/auth/login" in page.url
        if is_login_page:
            logger.info("📍 当前在登录页面，需要执行登录")
        else:
            logger.info("📍 已登录状态，无需重复登录")
        return is_login_page
    
    def _take_screenshot(self, page: Page, status: str):
        """智能截图保存"""
        try:
            time.sleep(3)  # 等待页面完全渲染
            
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            # 使用服务器ID作为文件名，避免特殊字符问题
            filename = f"{status}_{self.server_id}_{timestamp}.png"
            
            page.screenshot(path=filename)
            logger.info(f"📸 截图已保存: {filename}")
            
        except Exception as e:
            logger.error(f"❌ 截图保存失败: {str(e)}")


# =====================================================================
#                          主程序入口
# =====================================================================

def main():
    """主程序执行流程"""
    try:
        logger.info("🚀 开始执行 HidenCloud 自动登录脚本...")
        
        # 步骤1：创建登录客户端实例
        logger.info("📋 正在初始化登录客户端...")
        login_client = HidenCloudLogin()
        logger.info("✅ 登录客户端初始化完成")
        
        # 步骤2：确定浏览器运行模式
        is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
        headless = is_github_actions or os.getenv('HEADLESS', 'true').lower() == 'true'
        
        if headless:
            logger.info("👻 使用无头模式运行（适合CI/CD环境）")
        else:
            logger.info("🖥️  使用有界面模式运行（适合本地调试）")
        
        # 步骤3：执行智能登录流程
        logger.info("🔐 开始执行智能登录流程...")
        success = login_client.login(headless=headless)
        
        # 步骤4：生成README.md报告
        logger.info("📝 开始生成运行报告...")
        login_client.generate_readme()
        
        # 步骤5：处理执行结果
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
