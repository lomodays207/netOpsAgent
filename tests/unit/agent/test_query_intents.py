from src.agent.query_intents import detect_host_port_status_query


def test_detect_host_port_status_query_matches_single_host_port_status_request():
    result = detect_host_port_status_query("请帮我检查10.0.2.20 主机上的 8008 是否正常监听？")

    assert result == {"host": "10.0.2.20", "port": 8008}


def test_detect_host_port_status_query_ignores_how_to_question():
    result = detect_host_port_status_query("如何检查端口是否监听")

    assert result is None


def test_detect_host_port_status_query_ignores_connectivity_request():
    result = detect_host_port_status_query("10.0.1.10 到 10.0.2.20 的 8008 不通")

    assert result is None
