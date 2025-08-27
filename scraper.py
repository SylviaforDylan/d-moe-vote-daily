import requests
from bs4 import BeautifulSoup
import re
import time
import random
from config import WEIDIAN_URLS, REQUEST_TIMEOUT

# 使用代理池和用户代理轮换来绕过反爬虫
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/116.0"
]

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Referer': 'https://www.weidian.com/',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'DNT': '1'
    }

def scrape_weidian():
    results = {}
    
    for product, url in WEIDIAN_URLS.items():
        try:
            print(f"\n{'='*50}")
            print(f"开始爬取 {product} 产品: {url}")
            start_time = time.time()
            
            # 创建会话处理cookies和重定向
            session = requests.Session()
            session.headers.update(get_random_headers())
            
            # 尝试绕过反爬虫 - 先访问主页再访问目标页面
            try:
                # 先访问微店主页获取cookies
                home_response = session.get('https://www.weidian.com/', timeout=REQUEST_TIMEOUT)
                home_response.raise_for_status()
                print(f"主页访问成功, 状态码: {home_response.status_code}")
            except Exception as e:
                print(f"主页访问失败: {str(e)}")
            
            # 获取商品页面
            print(f"访问目标URL: {url}")
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            response.encoding = 'utf-8' if 'utf-8' in response.headers.get('Content-Type', '').lower() else 'gbk'
            
            # 检查是否被重定向到错误页面
            if 'abnormal/500' in response.url:
                print(f"被重定向到错误页面: {response.url}")
                # 尝试使用备用方案：直接解析短链接
                print("尝试直接解析短链接...")
                item_id = extract_item_id(url)
                if item_id:
                    product_url = f"https://weidian.com/item.html?itemID={item_id}"
                    print(f"构造商品URL: {product_url}")
                    response = session.get(product_url, timeout=REQUEST_TIMEOUT)
                    response.encoding = 'utf-8' if 'utf-8' in response.headers.get('Content-Type', '').lower() else 'gbk'
            
            html = response.text
            
            # 解析HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # 尝试查找销售数据
            sales_num = extract_sales_from_html(html, soup)
            
            if sales_num is not None:
                results[product] = sales_num
            else:
                results[product] = 0
                print("警告: 所有方法都未能提取销售数据")
            
            elapsed = time.time() - start_time
            print(f"{product} 爬取完成, 耗时: {elapsed:.2f}秒, 结果: {results[product]}")
            print('='*50)
                
        except Exception as e:
            print(f"爬取{product}出错: {str(e)}")
            import traceback
            traceback.print_exc()
            results[product] = 0
            
    return results

def extract_item_id(short_url):
    """从短链接中提取商品ID"""
    try:
        # 短链接格式: https://k.youshop10.com/O1k4Cbir
        # 提取路径部分
        path = short_url.split('/')[-1]
        # 解码商品ID（这里需要逆向工程，实际实现可能需要调整）
        # 这是一个简化的示例，实际可能需要更复杂的解码
        return path
    except:
        return None

def extract_sales_from_html(html, soup):
    """从HTML中提取销售数据"""
    sales_num = None
    
    # 方法1: 尝试查找销售数据标签
    sales_tags = soup.find_all(string=re.compile(r'销量'))
    for tag in sales_tags:
        # 向上查找包含销售数据的父元素
        parent = tag.find_parent()
        while parent:
            text = parent.get_text().strip()
            # 尝试匹配多种格式的销量文本
            matches = re.findall(r'销量[:：]?\s*(\d+)', text)
            if matches:
                sales_num = int(matches[0])
                print(f"在文本中找到销售数据: {sales_num}")
                return sales_num
            parent = parent.find_parent()
    
    # 方法2: 在JavaScript数据中查找
    print("未找到销售标签，尝试在JavaScript中查找")
    patterns = [
        r'"soldNum"\s*:\s*(\d+)',
        r'"sold_count"\s*:\s*(\d+)',
        r'"soldCount"\s*:\s*(\d+)',
        r'"salesNum"\s*:\s*(\d+)',
        r'"saleNum"\s*:\s*(\d+)',
        r'已售\D*(\d+)',
        r'销量\D*(\d+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            sales_num = int(match.group(1))
            print(f"使用正则 '{pattern}' 找到销售数据: {sales_num}")
            return sales_num
    
    # 方法3: 尝试解析JSON数据
    print("尝试解析JSON数据")
    json_pattern = r'window\.rawData\s*=\s*({.*?});'
    json_match = re.search(json_pattern, html, re.DOTALL)
    if json_match:
        try:
            import json
            json_data = json.loads(json_match.group(1))
            # 尝试在JSON结构中查找销售数据
            if 'item' in json_data and 'soldNum' in json_data['item']:
                sales_num = json_data['item']['soldNum']
                print(f"在JSON中找到销售数据: {sales_num}")
                return sales_num
        except:
            pass
    
    return None