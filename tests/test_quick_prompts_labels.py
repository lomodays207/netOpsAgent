"""
Bug Condition Exploration Test for Chat Page Label Corrections

**Validates: Requirements 2.1, 2.2, 2.3**

This test encodes the EXPECTED behavior for category labels.
- On UNFIXED code: This test MUST FAIL (confirms bug exists)
- On FIXED code: This test MUST PASS (confirms fix works)

Property 1: Bug Condition - 类别标签准确性验证
For any quick prompt category that was previously inaccurate, the displayed
category label SHALL match the accurate, descriptive label that clearly
reflects its functional scope.
"""

import re
from pathlib import Path
import pytest


def extract_quick_prompts_from_js(js_file_path: Path) -> list[dict]:
    """
    Extract QUICK_PROMPTS array from static/app.js file.
    
    Returns a list of dictionaries with 'category' and 'items' keys.
    """
    content = js_file_path.read_text(encoding='utf-8')
    
    # Find the QUICK_PROMPTS array definition
    # Pattern: const QUICK_PROMPTS = [ ... ];
    match = re.search(
        r'const\s+QUICK_PROMPTS\s*=\s*\[(.*?)\];',
        content,
        re.DOTALL
    )
    
    if not match:
        raise ValueError("Could not find QUICK_PROMPTS array in app.js")
    
    array_content = match.group(1)
    
    # Extract category values using regex
    # Pattern: category: 'value'
    categories = re.findall(r"category:\s*['\"]([^'\"]+)['\"]", array_content)
    
    if len(categories) != 3:
        raise ValueError(f"Expected 3 categories, found {len(categories)}")
    
    return [{'category': cat} for cat in categories]


class TestQuickPromptsLabels:
    """
    Bug Condition Exploration Tests
    
    These tests verify that category labels are accurate and descriptive.
    On unfixed code, these tests WILL FAIL, confirming the bug exists.
    """
    
    @pytest.fixture
    def quick_prompts(self):
        """Load QUICK_PROMPTS from static/app.js"""
        project_root = Path(__file__).parent.parent
        app_js_path = project_root / "static" / "app.js"
        
        if not app_js_path.exists():
            pytest.skip(f"app.js not found at {app_js_path}")
        
        return extract_quick_prompts_from_js(app_js_path)
    
    def test_category_1_network_fault_diagnosis(self, quick_prompts):
        """
        **Validates: Requirement 2.1**
        
        Property: First category label SHALL be "网络故障诊断"
        
        WHEN 用户查看聊天页面的快速提示区域
        THEN 第一个类别 SHALL 显示为 "网络故障诊断"，明确诊断范围
        
        Current buggy value: "故障诊断"
        Expected correct value: "网络故障诊断"
        
        This test WILL FAIL on unfixed code (expected behavior).
        """
        actual_category = quick_prompts[0]['category']
        expected_category = '网络故障诊断'
        
        assert actual_category == expected_category, (
            f"Category 1 label is inaccurate. "
            f"Expected: '{expected_category}' (明确诊断范围为网络相关), "
            f"Got: '{actual_category}' (未明确指出是网络故障诊断)"
        )
    
    def test_category_2_access_relation_query(self, quick_prompts):
        """
        **Validates: Requirement 2.2**
        
        Property: Second category label SHALL be "访问关系查询"
        
        WHEN 用户查看聊天页面的快速提示区域
        THEN 第二个类别 SHALL 显示为 "访问关系查询"，明确查询功能
        
        Current buggy value: "访问关系"
        Expected correct value: "访问关系查询"
        
        This test WILL FAIL on unfixed code (expected behavior).
        """
        actual_category = quick_prompts[1]['category']
        expected_category = '访问关系查询'
        
        assert actual_category == expected_category, (
            f"Category 2 label is inaccurate. "
            f"Expected: '{expected_category}' (强调查询功能), "
            f"Got: '{actual_category}' (未明确指出是查询功能)"
        )
    
    def test_category_3_ticket_knowledge_qa(self, quick_prompts):
        """
        **Validates: Requirement 2.3**
        
        Property: Third category label SHALL be "提单知识问答"
        
        WHEN 用户查看聊天页面的快速提示区域
        THEN 第三个类别 SHALL 显示为 "提单知识问答"，准确反映知识问答性质
        
        Current buggy value: "权限提单"
        Expected correct value: "提单知识问答"
        
        This test WILL FAIL on unfixed code (expected behavior).
        """
        actual_category = quick_prompts[2]['category']
        expected_category = '提单知识问答'
        
        assert actual_category == expected_category, (
            f"Category 3 label is inaccurate. "
            f"Expected: '{expected_category}' (准确描述为知识问答类型), "
            f"Got: '{actual_category}' (未准确反映其为知识问答性质)"
        )
    
    def test_all_categories_accurate_property(self, quick_prompts):
        """
        **Validates: Requirements 2.1, 2.2, 2.3**
        
        Property-Based Test: Category Label Accuracy
        
        FOR ALL categories in QUICK_PROMPTS WHERE isBugCondition(category):
            The displayed category label SHALL accurately reflect its functional scope
        
        This is a scoped property test that checks all three concrete failing cases.
        On unfixed code, this test WILL FAIL with counterexamples.
        """
        expected_categories = [
            '网络故障诊断',  # Requirement 2.1
            '访问关系查询',  # Requirement 2.2
            '提单知识问答',  # Requirement 2.3
        ]
        
        actual_categories = [prompt['category'] for prompt in quick_prompts]
        
        # Collect all mismatches as counterexamples
        counterexamples = []
        for i, (actual, expected) in enumerate(zip(actual_categories, expected_categories)):
            if actual != expected:
                counterexamples.append({
                    'index': i,
                    'expected': expected,
                    'actual': actual,
                })
        
        assert len(counterexamples) == 0, (
            f"Found {len(counterexamples)} inaccurate category labels:\n" +
            "\n".join([
                f"  - Category {ce['index']}: Expected '{ce['expected']}', Got '{ce['actual']}'"
                for ce in counterexamples
            ])
        )
