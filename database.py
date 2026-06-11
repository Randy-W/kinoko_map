from beanie import Document, Link, init_beanie
from pydantic import Field, BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from typing import Optional, List, Dict
import json
import pymongo
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "kinoko_map")

client: AsyncIOMotorClient = None
db = None


async def init_db():
    """初始化数据库连接"""
    global client, db
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    
    await init_beanie(
        database=db,
        document_models=[ArcadeStore, ActionToken, Drum]
    )
    
    await create_indexes()

    # await ActionToken.insert_one(ActionToken(key="114514", remaining_uses=50))



async def create_indexes():
    """创建数据库索引以提高查询性能"""
    await db["arcade_store"].create_index("province")
    await db["arcade_store"].create_index("city")
    await db["arcade_store"].create_index("district")
    await db["arcade_store"].create_index("available")
    await db["arcade_store"].create_index("created_at")
    await db["action_token"].create_index("key", unique=True)
    await db["drum"].create_index("store_id")
    await db["drum"].create_index("frame_version")


class ActionToken(Document):
    """操作Token模型 - 用于控制修改权限"""
    key: str = Field(unique=True)
    remaining_uses: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "action_token"


class Drum(Document):
    """鼓框体模型 - 存储机厅内的每个鼓"""
    store_id: str
    
    overall_cond_1p: Optional[str] = Field(default="nom")
    overall_cond_2p: Optional[str] = Field(default="nom")
    
    p1_x_l: Optional[str] = Field(default="")
    p1_o_l: Optional[str] = Field(default="")
    p1_o_r: Optional[str] = Field(default="")
    p1_x_r: Optional[str] = Field(default="")
    
    p2_x_l: Optional[str] = Field(default="")
    p2_o_l: Optional[str] = Field(default="")
    p2_o_r: Optional[str] = Field(default="")
    p2_x_r: Optional[str] = Field(default="")
    
    p1_audio: int = Field(default=0)
    p2_audio: int = Field(default=0)
    
    screen: str = Field(default="nom")
    track_no: int = Field(default=1)
    
    comm: Optional[str] = Field(default="")
    change_no: int = Field(default=0)
    last_change: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "drum"


class ArcadeStore(Document):
    id: str = Field(unique=True)
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    store_name: Optional[str] = None
    address: Optional[str] = None
    name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    abcode: Optional[str] = None
    price_range: Optional[str] = None
    business_hours: Optional[str] = None
    local_group: Optional[str] = None
    cab_count: Optional[int] = None
    available: Optional[bool] = True
    created_at: datetime = Field(default_factory=datetime.now)
    
    total_condition_score: int = Field(default=0)
    condition_rating_count: int = Field(default=0)
    total_recommendation_score: int = Field(default=0)
    recommendation_rating_count: int = Field(default=0)

    class Settings:
        name = "arcade_store"
