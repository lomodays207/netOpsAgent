"""
测试知识库文档在线预览功能

测试 DocumentProcessor.get_file_content() 方法
"""
import os
import sys
import tempfile
import shutil
import importlib.util
import pytest

# 直接导入 document_processor 模块，避免通过 rag/__init__.py 触发 chromadb 依赖
_module_path = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'rag', 'document_processor.py')
_spec = importlib.util.spec_from_file_location("document_processor", os.path.abspath(_module_path))
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
DocumentProcessor = _module.DocumentProcessor


class TestGetFileContent:
    """测试 DocumentProcessor.get_file_content 方法"""

    def setup_method(self):
        """每个测试前创建临时目录"""
        self.test_dir = tempfile.mkdtemp()
        self.processor = DocumentProcessor(documents_dir=self.test_dir)

    def teardown_method(self):
        """每个测试后清理临时目录"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_file_content_success(self):
        """测试正常读取文件内容"""
        doc_id = "doc_20260210_test1234"
        filename = "test_doc.txt"
        content = "这是一个测试文档的内容\n第二行内容"
        
        # 写入测试文件（使用二进制模式确保内容一致）
        safe_filename = f"{doc_id}_{filename}"
        file_path = os.path.join(self.test_dir, safe_filename)
        with open(file_path, "wb") as f:
            f.write(content.encode("utf-8"))

        # 读取并验证
        result = self.processor.get_file_content(doc_id)
        
        assert result is not None
        assert result["filename"] == filename
        assert result["content"] == content
        assert result["size"] > 0

    def test_get_file_content_not_found(self):
        """测试文件不存在时返回 None"""
        result = self.processor.get_file_content("doc_nonexistent_00000000")
        assert result is None

    def test_get_file_content_gbk_encoding(self):
        """测试 GBK 编码文件的读取"""
        doc_id = "doc_20260210_gbktest1"
        filename = "gbk_doc.txt"
        content = "这是GBK编码的中文内容"
        
        safe_filename = f"{doc_id}_{filename}"
        file_path = os.path.join(self.test_dir, safe_filename)
        with open(file_path, "wb") as f:
            f.write(content.encode("gbk"))

        result = self.processor.get_file_content(doc_id)
        
        assert result is not None
        assert result["filename"] == filename
        assert "GBK" in result["content"] or "中文" in result["content"]

    def test_get_file_content_empty_file(self):
        """测试空文件的读取"""
        doc_id = "doc_20260210_empty123"
        filename = "empty.txt"
        
        safe_filename = f"{doc_id}_{filename}"
        file_path = os.path.join(self.test_dir, safe_filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("")

        result = self.processor.get_file_content(doc_id)
        
        assert result is not None
        assert result["filename"] == filename
        assert result["content"] == ""
        assert result["size"] == 0

    def test_get_file_content_extracts_original_filename(self):
        """测试正确提取原始文件名（去掉 doc_id 前缀）"""
        doc_id = "doc_20260210191000_abcd1234"
        filename = "my_knowledge_base.txt"
        
        safe_filename = f"{doc_id}_{filename}"
        file_path = os.path.join(self.test_dir, safe_filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("test content")

        result = self.processor.get_file_content(doc_id)
        
        assert result is not None
        assert result["filename"] == filename


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
