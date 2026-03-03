"""
文档处理器

处理TXT文档的上传、分割和向量化
"""
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple


# 默认文档存储路径
DEFAULT_DOCUMENTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "runtime", "knowledge_base", "documents"
)


class TextSplitter:
    """
    文本分割器
    
    使用递归字符分割策略
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        separators: List[str] = None
    ):
        """
        初始化文本分割器
        
        Args:
            chunk_size: 块大小（字符数）
            chunk_overlap: 块重叠（字符数）
            separators: 分隔符列表
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]
    
    def split_text(self, text: str) -> List[str]:
        """
        分割文本，优先按Markdown标题分割
        
        Args:
            text: 输入文本
            
        Returns:
            分割后的文本块列表
        """
        if not text or not text.strip():
            return []

        # 1. 尝试按Markdown标题分割 (##, ###)
        # 简单的按行扫描实现
        lines = text.split('\n')
        chunks = []
        current_chunk = []
        current_length = 0
        
        for line in lines:
            is_header = line.strip().startswith('#')
            line_len = len(line) + 1 # +1 for newline
            
            # 如果是标题，且当前块已有内容，则强制分割（除非当前块非常小）
            if is_header and current_chunk and current_length > 50:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_length = line_len
            else:
                # 检查长度是否超限
                if current_length + line_len > self.chunk_size:
                    # 如果当前块非空，先保存
                    if current_chunk:
                        chunks.append('\n'.join(current_chunk))
                        current_chunk = []
                        current_length = 0
                    
                    # 如果单行过长，使用递归分割
                    if line_len > self.chunk_size:
                        sub_chunks = self._split_recursive(line, self.separators)
                        chunks.extend(sub_chunks)
                    else:
                        current_chunk = [line]
                        current_length = line_len
                else:
                    current_chunk.append(line)
                    current_length += line_len
        
        # 添加最后一个块
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
            
        return chunks
    
    def _split_recursive(self, text: str, separators: List[str]) -> List[str]:
        """递归分割文本"""
        if not separators:
            # 没有分隔符了，按字符数直接分割
            return self._split_by_chars(text)
        
        separator = separators[0]
        remaining_separators = separators[1:]
        
        if separator == "":
            return self._split_by_chars(text)
        
        # 按当前分隔符分割
        parts = text.split(separator)
        
        chunks = []
        for part in parts:
            if len(part) <= self.chunk_size:
                if part.strip():
                    chunks.append(part.strip())
            else:
                # 继续用下一个分隔符分割
                sub_chunks = self._split_recursive(part, remaining_separators)
                chunks.extend(sub_chunks)
        
        return chunks
    
    def _split_by_chars(self, text: str) -> List[str]:
        """按字符数分割"""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - self.chunk_overlap if end < len(text) else end
        return chunks
    
    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """合并过小的块"""
        if not chunks:
            return []
        
        min_chunk_size = self.chunk_size // 4  # 最小块大小为1/4
        merged = []
        current = ""
        
        for chunk in chunks:
            if len(current) + len(chunk) <= self.chunk_size:
                current = (current + " " + chunk).strip() if current else chunk
            else:
                if current:
                    merged.append(current)
                current = chunk
        
        if current:
            merged.append(current)
        
        return merged


class DocumentProcessor:
    """
    文档处理器
    
    处理TXT文档的上传、分割和存储
    """
    
    def __init__(
        self,
        documents_dir: str = None,
        chunk_size: int = 500,
        chunk_overlap: int = 100
    ):
        """
        初始化文档处理器
        
        Args:
            documents_dir: 文档存储目录
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
        """
        self.documents_dir = documents_dir or DEFAULT_DOCUMENTS_DIR
        self.text_splitter = TextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # 确保目录存在
        os.makedirs(self.documents_dir, exist_ok=True)
    
    def process_text_file(
        self,
        file_content: bytes,
        filename: str,
        encoding: str = "utf-8"
    ) -> Tuple[str, List[str], List[Dict[str, Any]]]:
        """
        处理TXT文件
        
        Args:
            file_content: 文件内容（字节）
            filename: 文件名
            encoding: 文件编码
            
        Returns:
            (doc_id, chunks, metadatas)
        """
        # 生成文档ID
        doc_id = f"doc_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # 解码文件内容
        try:
            text = file_content.decode(encoding)
        except UnicodeDecodeError:
            # 尝试其他编码
            for enc in ["gbk", "gb2312", "latin-1"]:
                try:
                    text = file_content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"无法解码文件 {filename}，请确保是有效的文本文件")
        
        # 保存原始文件
        saved_path = self._save_file(file_content, filename, doc_id)
        
        # 分割文本
        chunks = self.text_splitter.split_text(text)
        
        if not chunks:
            raise ValueError(f"文件 {filename} 内容为空或无法分割")
        
        # 生成元数据
        upload_time = datetime.now().isoformat()
        metadatas = []
        for i, chunk in enumerate(chunks):
            metadatas.append({
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "upload_time": upload_time,
                "saved_path": saved_path
            })
        
        print(f"[DocumentProcessor] 处理文件 {filename}: {len(chunks)} 个块")
        
        return doc_id, chunks, metadatas
    
    def _save_file(self, content: bytes, filename: str, doc_id: str) -> str:
        """保存原始文件"""
        # 使用doc_id作为文件名前缀，避免冲突
        safe_filename = f"{doc_id}_{filename}"
        file_path = os.path.join(self.documents_dir, safe_filename)
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        return file_path
    
    def get_file_content(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        读取文档内容用于预览
        
        Args:
            doc_id: 文档ID
            
        Returns:
            包含文件名和内容的字典，文件不存在时返回 None
        """
        # 在文档目录中查找匹配 doc_id 前缀的文件
        for file in os.listdir(self.documents_dir):
            if file.startswith(doc_id):
                file_path = os.path.join(self.documents_dir, file)
                if os.path.isfile(file_path):
                    # 提取原始文件名（去掉 doc_id_ 前缀）
                    original_filename = file[len(doc_id) + 1:]  # +1 for underscore
                    
                    # 读取文件内容，尝试多种编码
                    with open(file_path, "rb") as f:
                        raw_content = f.read()
                    
                    for encoding in ["utf-8", "gbk", "gb2312", "latin-1"]:
                        try:
                            text_content = raw_content.decode(encoding)
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        text_content = raw_content.decode("utf-8", errors="replace")
                    
                    return {
                        "filename": original_filename,
                        "content": text_content,
                        "size": len(raw_content)
                    }
        
        return None
    
    def delete_file(self, doc_id: str, filename: str = None) -> bool:
        """
        删除原始文件
        
        Args:
            doc_id: 文档ID
            filename: 文件名（可选）
            
        Returns:
            是否删除成功
        """
        # 查找并删除文件
        for file in os.listdir(self.documents_dir):
            if file.startswith(doc_id):
                file_path = os.path.join(self.documents_dir, file)
                try:
                    os.remove(file_path)
                    print(f"[DocumentProcessor] 删除文件: {file_path}")
                    return True
                except Exception as e:
                    print(f"[DocumentProcessor] 删除文件失败: {e}")
                    return False
        
        return False
    
    def list_files(self) -> List[Dict[str, Any]]:
        """
        列出所有已保存的文件
        
        Returns:
            文件信息列表
        """
        files = []
        for filename in os.listdir(self.documents_dir):
            file_path = os.path.join(self.documents_dir, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                files.append({
                    "filename": filename,
                    "size": stat.st_size,
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        return files
