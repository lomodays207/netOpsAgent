"""
诊断报告数据模型
定义最终输出的故障排查报告结构
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from .results import StepResult


@dataclass
class DiagnosticReport:
    """
    故障诊断报告

    包含排查的完整结果、根因分析和修复建议
    """
    task_id: str                        # 任务ID
    root_cause: str                     # 根因描述
    confidence: float                   # 置信度 (0.0-1.0)
    evidence: List[str]                 # 支持证据列表
    fix_suggestions: List[str]          # 修复建议列表
    need_human: bool                    # 是否需要人工介入
    executed_steps: List[StepResult]    # 执行的所有步骤
    total_time: float                   # 总耗时（秒）
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据

    def __str__(self) -> str:
        confidence_pct = self.confidence * 100
        human_flag = "🚨 需要人工介入" if self.need_human else "✅ 已定位"
        return (f"报告[{self.task_id}] - {human_flag}\n"
               f"根因: {self.root_cause}\n"
               f"置信度: {confidence_pct:.1f}%\n"
               f"总耗时: {self.total_time:.1f}s")

    def get_confidence_level(self) -> str:
        """获取置信度等级"""
        if self.confidence >= 0.9:
            return "高"
        elif self.confidence >= 0.7:
            return "中"
        else:
            return "低"

    def to_markdown(self) -> str:
        """
        生成Markdown格式的报告

        Returns:
            完整的Markdown报告字符串
        """
        confidence_pct = self.confidence * 100
        status_icon = "✅" if not self.need_human else "🚨"

        md = f"""# 网络故障排查报告

**任务ID**: {self.task_id}
**创建时间**: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}
**排查耗时**: {self._format_time(self.total_time)}
**状态**: {status_icon} {'需要人工深入排查' if self.need_human else '已定位根因'}

---

## 根因分析

**结论**: {self.root_cause}

**置信度**: {confidence_pct:.1f}% ({self.get_confidence_level()})

---

## 支持证据

"""
        for i, ev in enumerate(self.evidence, 1):
            md += f"{i}. {ev}\n"

        md += "\n---\n\n## 修复建议\n\n"

        for i, suggestion in enumerate(self.fix_suggestions, 1):
            md += f"{i}. {suggestion}\n"

        md += "\n---\n\n## 排查步骤详情\n\n"

        for step in self.executed_steps:
            status = "✅" if step.success else "❌"
            md += f"### Step {step.step_number}: {step.step_name} {status}\n\n"
            md += f"**动作**: {step.action}\n\n"

            if step.command_result:
                md += f"**命令**: `{step.command_result.command}`\n\n"
                md += f"**执行主机**: {step.command_result.host}\n\n"
                md += f"**耗时**: {step.command_result.execution_time:.2f}s\n\n"

                if step.command_result.stdout:
                    md += "**输出**:\n```\n"
                    # 限制输出长度，避免报告过长
                    output = step.command_result.stdout[:500]
                    if len(step.command_result.stdout) > 500:
                        output += "\n... (输出已截断)"
                    md += output
                    md += "\n```\n\n"

                if step.command_result.stderr:
                    md += "**错误输出**:\n```\n"
                    md += step.command_result.stderr[:200]
                    md += "\n```\n\n"

            if step.metadata:
                md += f"**分析结果**: {step.metadata}\n\n"

            md += "---\n\n"

        return md

    def _format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        else:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}分{secs}秒"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "task_id": self.task_id,
            "root_cause": self.root_cause,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "fix_suggestions": self.fix_suggestions,
            "need_human": self.need_human,
            "executed_steps": [step.to_dict() for step in self.executed_steps],
            "total_time": self.total_time,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "DiagnosticReport":
        """
        从JSON数据创建DiagnosticReport

        用于从LLM的JSON响应构建报告对象
        """
        return cls(
            task_id=data.get("task_id", ""),
            root_cause=data.get("root_cause", ""),
            confidence=data.get("confidence", 0.0),
            evidence=data.get("evidence", []),
            fix_suggestions=data.get("fix_suggestions", []),
            need_human=data.get("need_human", False),
            executed_steps=[],  # 从JSON恢复时通常不包含完整步骤
            total_time=data.get("total_time", 0.0),
            metadata=data.get("metadata", {})
        )
