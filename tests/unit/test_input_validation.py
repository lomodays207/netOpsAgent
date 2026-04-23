import pytest

from src.utils.input_validator import (
    extract_endpoint_pair,
    extract_network_info,
    is_valid_ip,
    is_valid_port,
)


class DummyLLMClient:
    def invoke_with_json(self, **kwargs):
        raise RuntimeError("LLM should not be called in fallback parser tests")


class TestIPValidation:
    def test_valid_ip(self):
        assert is_valid_ip("10.0.1.10") is True
        assert is_valid_ip("192.168.1.1") is True
        assert is_valid_ip("127.0.0.1") is True
        assert is_valid_ip("0.0.0.0") is True
        assert is_valid_ip("255.255.255.255") is True

    def test_invalid_ip(self):
        assert is_valid_ip("10.1.10") is False
        assert is_valid_ip("10.0.2") is False
        assert is_valid_ip("256.0.0.1") is False
        assert is_valid_ip("10.0.1.256") is False
        assert is_valid_ip("") is False
        assert is_valid_ip("abc.def.ghi.jkl") is False
        assert is_valid_ip("10.0.1.10.20") is False

    def test_valid_port(self):
        assert is_valid_port(80) is True
        assert is_valid_port(443) is True
        assert is_valid_port(1) is True
        assert is_valid_port(65535) is True
        assert is_valid_port(None) is True

    def test_invalid_port(self):
        assert is_valid_port(0) is False
        assert is_valid_port(-1) is False
        assert is_valid_port(65536) is False
        assert is_valid_port(100000) is False

    def test_extract_valid_network_info(self):
        source, target, port, error = extract_network_info("10.0.1.10到10.0.2.20端口80不通")
        assert source == "10.0.1.10"
        assert target == "10.0.2.20"
        assert port == 80
        assert error == ""

        source, target, port, error = extract_network_info("10.0.1.10到10.0.2.20不通")
        assert source == "10.0.1.10"
        assert target == "10.0.2.20"
        assert port is None
        assert error == ""

    def test_extract_hostname_network_info(self):
        source, target, port, error = extract_network_info("web-01到db-01端口3306连接失败")
        assert source == "web-01"
        assert target == "db-01"
        assert port == 3306
        assert error == ""

        source, target, port, error = extract_network_info("应用服务器访问数据库失败")
        assert source == "应用服务器"
        assert target == "数据库"
        assert port is None
        assert error == ""

    def test_extract_endpoint_pair_stops_before_connected_unreachable_phrase(self):
        source, target = extract_endpoint_pair("web-01到db-01连不通")

        assert source == "web-01"
        assert target == "db-01"

    def test_extract_network_info_stops_before_connected_unreachable_phrase(self):
        source, target, port, error = extract_network_info("web-01到db-01连不通")

        assert source == "web-01"
        assert target == "db-01"
        assert port is None
        assert error == ""

    def test_extract_invalid_source_ip(self):
        source, target, port, error = extract_network_info("10.1.10到10.0.2.20端口80不通")
        assert source is None
        assert target is None
        assert port is None
        assert "源IP地址格式不正确" in error
        assert "10.1.10" in error

    def test_extract_invalid_target_ip(self):
        source, target, port, error = extract_network_info("10.0.1.10到10.0.2端口80不通")
        assert source is None
        assert target is None
        assert port is None
        assert "目标IP地址格式不正确" in error
        assert "10.0.2" in error

    def test_extract_invalid_port(self):
        source, target, port, error = extract_network_info("10.0.1.10到10.0.2.20端口99999不通")
        assert source is None
        assert target is None
        assert port is None
        assert "端口号超出有效范围" in error
        assert "99999" in error

    def test_extract_missing_info(self):
        source, target, port, error = extract_network_info("10.0.1.10")
        assert source is None
        assert target is None
        assert port is None
        assert "无法识别源和目标端点" in error


class TestNLUWithValidation:
    def test_nlu_invalid_ip_raises_error(self):
        from src.agent.nlu import NLU

        nlu = NLU(llm_client=DummyLLMClient())

        with pytest.raises(ValueError) as exc_info:
            nlu._fallback_rule_based_parse("10.1.10到10.0.2.20端口80不通", "test_001")

        assert "源IP地址格式不正确" in str(exc_info.value)

    def test_nlu_allows_hostnames(self):
        from src.agent.nlu import NLU

        nlu = NLU(llm_client=DummyLLMClient())
        task = nlu._fallback_rule_based_parse("web-01到db-01端口3306连接失败", "test_002")

        assert task.source == "web-01"
        assert task.target == "db-01"
        assert task.port == 3306


class TestCLIWithValidation:
    def test_cli_invalid_ip_raises_error(self):
        from src.cli import parse_user_input

        with pytest.raises(ValueError) as exc_info:
            parse_user_input("10.1.10到10.0.2.20端口80不通")
        assert "源IP地址格式不正确" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            parse_user_input("10.0.1.10到10.0.2端口80不通")
        assert "目标IP地址格式不正确" in str(exc_info.value)
