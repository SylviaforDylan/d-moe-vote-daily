from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class SaleData(Base):
    __tablename__ = 'sale_data'
    id = Column(Integer, primary_key=True)
    product = Column(String(20))  # 'blue' 或 'red'
    sales = Column(Integer)
    timestamp = Column(DateTime, default=datetime.now)

# 初始化数据库
def init_db():
    engine = create_engine('sqlite:///weidian.db')
    Base.metadata.create_all(engine)
    return engine

# 获取数据库会话
def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()