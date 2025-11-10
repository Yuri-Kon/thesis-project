# 定义标准化数据结构

from pydantic import BaseModel, Field
from typing import Optional, Tuple, Dict, Any

# 定义系统输入：任务的统一格式
class ProteinDesignTask(BaseModel):
    task_id: str
    goal: str
    constrains: Dict[str, Any] = Field(default_factory=dict)

# 定义系统输出：任务结果的统一格式
class DesignResult:
    task_id: str
    sequence: Optional[str] = None # 生成的蛋白质的序列
    structure_pbd_path: Optional[str] = None # 生成的三维结构文件路径
    scores: Dict[str, float] = Field(default_factory=dict) # 各种评分指标
    risk_flags: Dict[str, str] = Field(default_factory=dict) # 安全检查结果
