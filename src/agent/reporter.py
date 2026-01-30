"""
报告生成器

生成Markdown格式的故障排查报告
"""
from pathlib import Path

from ..models.report import DiagnosticReport


class ReportGenerator:
    """
    报告生成器

    Phase 1实现：生成Markdown文件
    Phase 2实现：支持多种格式（PDF、HTML、JSON等）
    """

    def __init__(self, output_dir: str = "runtime/reports"):
        """
        初始化报告生成器

        Args:
            output_dir: 报告输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, report: DiagnosticReport) -> str:
        """
        生成报告文件

        Args:
            report: 诊断报告对象

        Returns:
            生成的报告文件路径
        """
        # 生成Markdown内容
        markdown_content = report.to_markdown()

        # 生成文件名
        filename = f"diagnostic_report_{report.task_id}.md"
        output_path = self.output_dir / filename

        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        return str(output_path)

    def generate_summary(self, report: DiagnosticReport) -> str:
        """
        生成简要摘要（用于终端输出）

        Args:
            report: 诊断报告对象

        Returns:
            摘要文本
        """
        confidence_pct = report.confidence * 100
        status_icon = "[OK]" if not report.need_human else "[WARN]"

        summary = f"""
{'='*60}
网络故障排查报告 - {report.task_id}
{'='*60}

状态: {status_icon} {'已定位根因' if not report.need_human else '需要人工介入'}
置信度: {confidence_pct:.1f}% ({report.get_confidence_level()})
总耗时: {report.total_time:.1f}秒

根因分析:
{report.root_cause}

修复建议:
"""
        for i, suggestion in enumerate(report.fix_suggestions, 1):
            summary += f"{i}. {suggestion}\n"

        summary += f"\n详细报告已生成，请查看完整报告文件。\n"
        summary += "=" * 60

        return summary
