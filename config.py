# 微店链接配置
WEIDIAN_URLS = {
    "blue": "https://k.youshop10.com/cdlExdO5",
    "red": "https://k.youshop10.com/Dc8NZYIe"
}

# 数据库配置
DATABASE_URI = 'sqlite:///weidian.db'

# 爬取间隔（秒）
SCRAPE_INTERVAL = 300  # 5分钟

# 请求超时时间（秒）
REQUEST_TIMEOUT = 30

# 15分钟数据保存文件
FIFTEEN_MIN_DATA_FILE = 'fifteen_min_data.json'