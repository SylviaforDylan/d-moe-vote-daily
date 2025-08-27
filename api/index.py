from flask import Flask, render_template, jsonify
from database import init_db, get_session, SaleData
from scraper import scrape_weidian
import datetime
import logging
import os
import json

# 配置日志 - 只输出到控制台，不写入文件
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

app = Flask(__name__)
engine = init_db()
logger = logging.getLogger(__name__)

# 存储15分钟间隔的数据
fifteen_min_data = {
    'blue': {'timestamps': [], 'sales': [], 'increments': []},
    'red': {'timestamps': [], 'sales': [], 'increments': []}
}

# 存储最后一次销售数据用于计算增量
last_sales = {'blue': None, 'red': None}

def load_fifteen_min_data():
    """从文件加载15分钟间隔数据"""
    try:
        # 在Vercel环境中，使用/tmp目录存储临时文件
        data_file = '/tmp/fifteen_min_data.json'
        if os.path.exists(data_file):
            with open(data_file, 'r') as f:
                data = json.load(f)
                # 转换时间字符串为datetime对象
                for color in ['blue', 'red']:
                    if color in data:
                        data[color]['timestamps'] = [
                            datetime.datetime.fromisoformat(ts) 
                            for ts in data[color]['timestamps']
                        ]
                return data
    except Exception as e:
        logger.error(f"加载数据文件失败: {str(e)}")
    return {
        'blue': {'timestamps': [], 'sales': [], 'increments': []},
        'red': {'timestamps': [], 'sales': [], 'increments': []}
    }

def save_fifteen_min_data():
    """保存15分钟间隔数据到文件"""
    try:
        # 准备可序列化的数据
        save_data = {}
        for color in ['blue', 'red']:
            save_data[color] = {
                'timestamps': [ts.isoformat() for ts in fifteen_min_data[color]['timestamps']],
                'sales': fifteen_min_data[color]['sales'],
                'increments': fifteen_min_data[color]['increments']
            }
        
        # 在Vercel环境中，使用/tmp目录存储临时文件
        data_file = '/tmp/fifteen_min_data.json'
        with open(data_file, 'w') as f:
            json.dump(save_data, f, indent=2)
    except Exception as e:
        logger.error(f"保存数据文件失败: {str(e)}")

def update_fifteen_min_data(product, sales, timestamp):
    """更新15分钟间隔数据"""
    global fifteen_min_data, last_sales
    
    # 如果是第一次记录
    if last_sales[product] is None:
        last_sales[product] = sales
        fifteen_min_data[product]['timestamps'].append(timestamp)
        fifteen_min_data[product]['sales'].append(sales)
        fifteen_min_data[product]['increments'].append(0)
        save_fifteen_min_data()
        return
    
    # 计算增量
    increment = sales - last_sales[product]
    
    # 检查是否有历史数据点
    if fifteen_min_data[product]['timestamps']:
        last_timestamp = fifteen_min_data[product]['timestamps'][-1]
        time_diff = (timestamp - last_timestamp).total_seconds()
        
        # 如果距离上次记录不足15分钟，不更新
        if time_diff < 900:  # 900秒 = 15分钟
            return
    
    # 更新数据
    fifteen_min_data[product]['timestamps'].append(timestamp)
    fifteen_min_data[product]['sales'].append(sales)
    fifteen_min_data[product]['increments'].append(increment)
    
    # 更新最后销售数据
    last_sales[product] = sales
    
    # 保存到文件
    save_fifteen_min_data()

# 启动时加载数据
fifteen_min_data = load_fifteen_min_data()

# 初始化最后销售数据
for product in ['blue', 'red']:
    if fifteen_min_data[product]['sales']:
        last_sales[product] = fifteen_min_data[product]['sales'][-1]
    else:
        last_sales[product] = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scrape')
def api_scrape():
    """API端点用于手动触发爬取"""
    session = get_session(engine)
    try:
        logger.info("开始执行手动爬取任务")
        start_time = datetime.datetime.now()
        
        sales_data = scrape_weidian()
        logger.info(f"爬取结果: {sales_data}")
        
        current_time = datetime.datetime.now()
        
        for product, sales in sales_data.items():
            # 保存原始数据到数据库
            new_record = SaleData(product=product, sales=sales, timestamp=current_time)
            session.add(new_record)
            
            # 更新15分钟间隔数据
            update_fifteen_min_data(product, sales, current_time)
        
        session.commit()
        
        elapsed = (datetime.datetime.now() - start_time).total_seconds()
        logger.info(f"数据更新成功, 耗时: {elapsed:.2f}秒")
        
        return jsonify({
            'status': 'success',
            'message': f'数据更新成功, 耗时: {elapsed:.2f}秒',
            'data': sales_data
        })
    except Exception as e:
        logger.error(f"手动爬取出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    finally:
        session.close()

@app.route('/api/realtime-data')
def realtime_data():
    session = get_session(engine)
    try:
        # 获取最近1.5小时内的所有数据（90分钟）
        time_threshold = datetime.datetime.now() - datetime.timedelta(minutes=150)
        
        # 查询蓝/红最近数据
        blue_data = session.query(SaleData).filter(
            SaleData.product == 'blue',
            SaleData.timestamp >= time_threshold
        ).order_by(SaleData.timestamp.asc()).all()
        
        red_data = session.query(SaleData).filter(
            SaleData.product == 'red',
            SaleData.timestamp >= time_threshold
        ).order_by(SaleData.timestamp.asc()).all()
        
        # 格式化数据
        def format_data(records):
            return [{
                'x': record.timestamp.isoformat(),
                'y': record.sales
            } for record in records]
        
        return jsonify({
            'blue': format_data(blue_data),
            'red': format_data(red_data),
            'last_updated': datetime.datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取实时数据出错: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
        
@app.route('/api/data')
def get_data():
    try:
        # 获取当前销售数据
        blue_current = last_sales.get('blue', 0) or 0
        red_current = last_sales.get('red', 0) or 0
        
        # 确保所有时间戳都是字符串格式
        blue_timestamps = [ts.isoformat() if isinstance(ts, datetime.datetime) else ts 
                          for ts in fifteen_min_data['blue']['timestamps']]
        red_timestamps = [ts.isoformat() if isinstance(ts, datetime.datetime) else ts 
                         for ts in fifteen_min_data['red']['timestamps']]
        
        return jsonify({
            'blue': {
                'timestamps': blue_timestamps,
                'sales': fifteen_min_data['blue']['sales'],
                'current': blue_current
            },
            'red': {
                'timestamps': red_timestamps,
                'sales': fifteen_min_data['red']['sales'],
                'current': red_current
            },
            'blue_increment': {
                'timestamps': blue_timestamps,
                'increments': fifteen_min_data['blue']['increments']
            },
            'red_increment': {
                'timestamps': red_timestamps,
                'increments': fifteen_min_data['red']['increments']
            },
            'last_updated': datetime.datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取数据出错: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Vercel需要这个变量
app = app