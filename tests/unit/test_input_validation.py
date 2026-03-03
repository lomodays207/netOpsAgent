"""
测试IP地址输入验证功能

验证当用户输入无效IP时，系统会返回友好的错误提示
"""
import pytest
from src.utils.input_validator import is_valid_ip, is_valid_port, extract_network_info


class TestIPValidation:
    """IP地址验证测试"""
    
    def test_valid_ip(self):
        """测试有效的IP地址"""
        assert is_valid_ip("10.0.1.10") == True
        assert is_valid_ip("192.168.1.1") == True
        assert is_valid_ip("127.0.0.1") == True
        assert is_valid_ip("0.0.0.0") == True
        assert is_valid_ip("255.255.255.255") == True
    
    def test_invalid_ip(self):
        """测试无效的IP地址"""
        assert is_valid_ip("10.1.10") == False  # 缺少一个字段
        assert is_valid_ip("10.0.2") == False  # 只有3个字段
        assert is_valid_ip("256.0.0.1") == False  # 超出范围
        assert is_valid_ip("10.0.1.256") == False  # 最后一个字段超范围
        assert is_valid_ip("") == False  # 空字符串
        assert is_valid_ip("abc.def.ghi.jkl") == False  # 非数字
        assert is_valid_ip("10.0.1.10.20") == False  # 5个字段
    
    def test_valid_port(self):
        """测试有效的端口号"""
        assert is_valid_port(80) == True
        assert is_valid_port(443) == True
        assert is_valid_port(1) == True
        assert is_valid_port(65535) == True
        assert is_valid_port(None) == True  # None是有效的（可选）
    
    def test_invalid_port(self):
        """测试无效的端口号"""
        assert is_valid_port(0) == False
        assert is_valid_port(-1) == False
        assert is_valid_port(65536) == False
        assert is_valid_port(100000) == False
    
    def test_extract_valid_network_info(self):
        """测试从有效输入中提取网络信息"""
        # 正确的输入
        source, target, port, error = extract_network_info("10.0.1.10到10.0.2.20端口80不通")
        assert source == "10.0.1.10"
        assert target == "10.0.2.20"
        assert port == 80
        assert error == ""
        
        # 没有端口号
        source, target, port, error = extract_network_info("10.0.1.10到10.0.2.20不通")
        assert source == "10.0.1.10"
        assert target == "10.0.2.20"
        assert port is None
        assert error == ""
    
    def test_extract_invalid_source_ip(self):
        """测试无效的源IP"""
        source, target, port, error = extract_network_info("10.1.10到10.0.2.20端口80不通")
        assert source is None
        assert target is None
        assert port is None
        assert "源IP地址格式不正确" in error
        assert "10.1.10" in error
    
    def test_extract_invalid_target_ip(self):
        """测试无效的目标IP"""
        source, target, port, error = extract_network_info("10.0.1.10到10.0.2端口80不通")
        assert source is None
        assert target is None
        assert port is None
        assert "目标IP地址格式不正确" in error
        assert "10.0.2" in error
    
    def test_extract_invalid_port(self):
        """测试无效的端口号"""
        source, target, port, error = extract_network_info("10.0.1.10到10.0.2.20端口99999不通")
        assert source is None
        assert target is None
        assert port is None
        assert "端口号超出有效范围" in error
        assert "99999" in error
    
    def test_extract_missing_info(self):
        """测试信息不完整"""
        source, target, port, error = extract_network_info("10.0.1.10")
        assert source is None
        assert target is None
        assert port is None
        assert "无法识别源IP和目标IP" in error


class TestNLUWithValidation:
    """测试NLU模块集成了IP验证"""
    
    def test_nlu_invalid_ip_raises_error(self):
        """测试NLU解析无效IP时抛出ValueError"""
        from src.agent.nlu import NLU
        
        nlu = NLU()
        
        # 当LLM解析失败时会回退到规则解析，此时应该抛出ValueError
        with pytest.raises(ValueError) as exc_info:
            # 使用一个明确会导致错误的输入
            # 注意：NLU会先尝试LLM，如果失败才会回退到规则解析
            # 为了确保测试规则解析，我们直接调用_fallback_rule_based_parse
            nlu._fallback_rule_based_parse("10.1.10到10.0.2.20端口80不通", "test_001")
        
        assert "源IP地址格式不正确" in str(exc_info.value)


class TestCLIWithValidation:
    """测试CLI模块集成了IP验证"""
    
    def test_cli_invalid_ip_raises_error(self):
        """测试CLI解析无效IP时抛出ValueError"""
        from src.cli import parse_user_input
        
        # 测试无效的源IP
        with pytest.raises(ValueError) as exc_info:
            parse_user_input("10.1.10到10.0.2.20端口80不通")
        
        assert "源IP地址格式不正确" in str(exc_info.value)
        
        # 测试无效的目标IP
        with pytest.raises(ValueError) as exc_info:
            parse_user_input("10.0.1.10到10.0.2端口80不通")
        
        assert "目标IP地址格式不正确" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
