"""
Unit Tests for is_access_relation_data_query Detection Function

Tests the detection logic that distinguishes between:
- Access relation DATA queries (should skip RAG)
- Access relation KNOWLEDGE queries (should use RAG)
- General questions (should use RAG)
"""
import pytest
from src.api import is_access_relation_data_query


class TestAccessRelationDataQueryDetection:
    """Test cases for access relation data query detection"""
    
    # ========================================================================
    # Positive Cases - Should Return True (Data Queries)
    # ========================================================================
    
    def test_system_code_outbound_query(self):
        """System code with outbound query pattern"""
        assert is_access_relation_data_query("N-CRM有哪些访问关系") is True
        assert is_access_relation_data_query("N-OA有哪些访问关系") is True
        assert is_access_relation_data_query("P-DB-MAIN有哪些访问关系") is True
    
    def test_system_code_inbound_query(self):
        """System code with inbound query pattern"""
        assert is_access_relation_data_query("哪些系统访问N-CRM") is True
        assert is_access_relation_data_query("N-OA被哪些系统访问") is True
    
    def test_system_code_bidirectional_query(self):
        """System code with bidirectional query pattern"""
        assert is_access_relation_data_query("N-CRM和N-OA之间有哪些访问关系") is True
    
    def test_deploy_unit_query(self):
        """Deploy unit query pattern"""
        assert is_access_relation_data_query("CRMJS_AP部署单元有哪些访问关系") is True
        assert is_access_relation_data_query("OAJS_WEB部署单元有哪些访问关系") is True
    
    def test_system_name_query(self):
        """System name (Chinese) query pattern"""
        assert is_access_relation_data_query("客户关系管理系统有哪些访问关系") is True
        assert is_access_relation_data_query("办公自动化系统有哪些访问关系") is True
        # Test system names without "系统" suffix
        assert is_access_relation_data_query("客户关系管理有哪些访问关系") is True
        assert is_access_relation_data_query("办公自动化有哪些访问关系") is True
    
    def test_various_relation_query_patterns(self):
        """Various ways to ask about access relations"""
        assert is_access_relation_data_query("N-CRM访问哪些系统") is True
        assert is_access_relation_data_query("N-CRM被哪些系统访问") is True
    
    # ========================================================================
    # Negative Cases - Should Return False (Knowledge Queries)
    # ========================================================================
    
    def test_knowledge_query_how_to(self):
        """Knowledge queries with 'how to' pattern"""
        assert is_access_relation_data_query("访问关系如何开权限") is False
        assert is_access_relation_data_query("如何申请访问关系") is False
        assert is_access_relation_data_query("怎么提单申请访问关系") is False
    
    def test_knowledge_query_process(self):
        """Knowledge queries about process"""
        assert is_access_relation_data_query("访问关系管理流程是什么") is False
        assert is_access_relation_data_query("访问关系审批流程") is False
    
    def test_knowledge_query_permissions(self):
        """Knowledge queries about permissions"""
        assert is_access_relation_data_query("访问关系权限如何配置") is False
        assert is_access_relation_data_query("N-CRM的访问权限如何申请") is False
    
    # ========================================================================
    # Negative Cases - Should Return False (General Questions)
    # ========================================================================
    
    def test_general_network_question(self):
        """General network operations questions"""
        assert is_access_relation_data_query("如何排查网络故障") is False
        assert is_access_relation_data_query("网络连接不通怎么办") is False
    
    def test_no_system_identifier(self):
        """Queries without system identifier"""
        assert is_access_relation_data_query("有哪些访问关系") is False
        assert is_access_relation_data_query("访问关系是什么") is False
    
    def test_no_relation_query_pattern(self):
        """Queries with system identifier but no relation query pattern"""
        assert is_access_relation_data_query("N-CRM是什么系统") is False
        assert is_access_relation_data_query("N-CRM的功能有哪些") is False
    
    # ========================================================================
    # Edge Cases
    # ========================================================================
    
    def test_mixed_query_data_and_knowledge(self):
        """Mixed query with both data and knowledge aspects"""
        # When both patterns present, knowledge pattern takes precedence (should return False)
        assert is_access_relation_data_query("N-CRM有哪些访问关系？另外如何开权限？") is False
    
    def test_empty_message(self):
        """Empty message"""
        assert is_access_relation_data_query("") is False
    
    def test_case_sensitivity(self):
        """Test case sensitivity of patterns"""
        assert is_access_relation_data_query("n-crm有哪些访问关系") is False  # lowercase system code
        assert is_access_relation_data_query("N-CRM有哪些访问关系") is True   # uppercase system code
    
    def test_whitespace_variations(self):
        """Test with various whitespace"""
        assert is_access_relation_data_query("N-CRM 有哪些访问关系") is True
        assert is_access_relation_data_query("N-CRM  有哪些访问关系") is True
    
    # ========================================================================
    # Real-world Examples
    # ========================================================================
    
    def test_real_world_data_queries(self):
        """Real-world examples of data queries"""
        queries = [
            "N-CRM有哪些访问关系",
            "CRMJS_AP部署单元有哪些访问关系",
            "哪些系统访问N-OA",
            "N-CRM和N-OA之间有哪些访问关系",
            "客户关系管理系统有哪些访问关系",
            "客户关系管理有哪些访问关系",  # Without "系统" suffix
            "办公自动化有哪些访问关系",      # Without "系统" suffix
            "P-DB-MAIN被哪些系统访问",
        ]
        for query in queries:
            assert is_access_relation_data_query(query) is True, f"Failed for: {query}"
    
    def test_real_world_knowledge_queries(self):
        """Real-world examples of knowledge queries"""
        queries = [
            "访问关系如何开权限",
            "如何提单申请访问关系",
            "访问关系管理流程是什么",
            "N-CRM的访问权限如何申请",
            "访问关系审批流程",
            "怎么配置访问关系",
        ]
        for query in queries:
            assert is_access_relation_data_query(query) is False, f"Failed for: {query}"
    
    def test_real_world_general_questions(self):
        """Real-world examples of general questions"""
        queries = [
            "如何排查网络故障",
            "网络连接不通怎么办",
            "ping不通怎么排查",
            "你好，请问你能做什么",
        ]
        for query in queries:
            assert is_access_relation_data_query(query) is False, f"Failed for: {query}"
