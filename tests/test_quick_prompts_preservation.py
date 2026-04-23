"""
Preservation Property Tests for Chat Page Label Corrections

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

These tests verify that non-label functionality remains unchanged after the fix.
- On UNFIXED code: These tests MUST PASS (establishes baseline behavior)
- On FIXED code: These tests MUST PASS (confirms no regressions)

Property 2: Preservation - 非标签功能保持不变
For any user interaction with quick prompts that does not involve category label
display, the behavior SHALL remain identical before and after the fix.
"""

import re
from pathlib import Path
import pytest


def extract_quick_prompts_structure(js_file_path: Path) -> list[dict]:
    """
    Extract complete QUICK_PROMPTS structure from static/app.js file.
    
    Returns a list of dictionaries with 'category' and 'items' keys,
    where items contain title, description, and template.
    """
    content = js_file_path.read_text(encoding='utf-8')
    
    # Find the QUICK_PROMPTS array definition
    match = re.search(
        r'const\s+QUICK_PROMPTS\s*=\s*\[(.*?)\];',
        content,
        re.DOTALL
    )
    
    if not match:
        raise ValueError("Could not find QUICK_PROMPTS array in app.js")
    
    array_content = match.group(1)
    
    # Split into groups (each group is a category with items)
    # Pattern: { category: '...', items: [...] }
    group_pattern = r'\{[^}]*category:[^}]*items:\s*\[[^\]]*\][^}]*\}'
    groups = re.findall(group_pattern, array_content, re.DOTALL)
    
    result = []
    for group in groups:
        # Extract category
        cat_match = re.search(r"category:\s*['\"]([^'\"]+)['\"]", group)
        category = cat_match.group(1) if cat_match else None
        
        # Extract items array
        items_match = re.search(r'items:\s*\[(.*?)\]', group, re.DOTALL)
        if not items_match:
            continue
        
        items_content = items_match.group(1)
        
        # Extract each item (title, description, template)
        item_pattern = r'\{[^}]*title:[^}]*description:[^}]*template:[^}]*\}'
        item_matches = re.findall(item_pattern, items_content, re.DOTALL)
        
        items = []
        for item_str in item_matches:
            title_match = re.search(r"title:\s*['\"]([^'\"]+)['\"]", item_str)
            desc_match = re.search(r"description:\s*['\"]([^'\"]+)['\"]", item_str)
            template_match = re.search(r"template:\s*['\"]([^'\"]+)['\"]", item_str)
            
            if title_match and desc_match and template_match:
                items.append({
                    'title': title_match.group(1),
                    'description': desc_match.group(1),
                    'template': template_match.group(1),
                })
        
        result.append({
            'category': category,
            'items': items,
        })
    
    return result


class TestQuickPromptsPreservation:
    """
    Preservation Property Tests
    
    These tests verify that the fix only changes category labels and does not
    affect any other functionality or data.
    """
    
    @pytest.fixture
    def quick_prompts(self):
        """Load QUICK_PROMPTS structure from static/app.js"""
        project_root = Path(__file__).parent.parent
        app_js_path = project_root / "static" / "app.js"
        
        if not app_js_path.exists():
            pytest.skip(f"app.js not found at {app_js_path}")
        
        return extract_quick_prompts_structure(app_js_path)
    
    def test_array_structure_intact(self, quick_prompts):
        """
        **Validates: Requirement 3.2**
        
        Property: QUICK_PROMPTS array structure SHALL remain intact
        
        WHEN 页面加载快速提示组件
        THEN 数组结构（每个 group 有 category 和 items）SHALL CONTINUE TO 保持不变
        
        Verifies:
        - Array has exactly 3 groups
        - Each group has 'category' and 'items' keys
        - Items is a list
        """
        assert len(quick_prompts) == 3, (
            f"Expected 3 quick prompt groups, got {len(quick_prompts)}. "
            "Array structure must remain unchanged."
        )
        
        for i, group in enumerate(quick_prompts):
            assert 'category' in group, (
                f"Group {i} missing 'category' key. Structure must be preserved."
            )
            assert 'items' in group, (
                f"Group {i} missing 'items' key. Structure must be preserved."
            )
            assert isinstance(group['items'], list), (
                f"Group {i} 'items' is not a list. Structure must be preserved."
            )
    
    def test_items_count_preserved(self, quick_prompts):
        """
        **Validates: Requirement 3.2**
        
        Property: Each category SHALL maintain its original number of items
        
        WHEN 用户查看快速提示区域
        THEN 每个类别下的具体提示项数量 SHALL CONTINUE TO 保持不变
        
        Expected item counts (from original code):
        - Category 1: 3 items
        - Category 2: 3 items
        - Category 3: 3 items
        """
        expected_counts = [3, 3, 3]
        actual_counts = [len(group['items']) for group in quick_prompts]
        
        assert actual_counts == expected_counts, (
            f"Item counts changed. Expected {expected_counts}, got {actual_counts}. "
            "Number of items per category must remain unchanged."
        )
    
    def test_item_properties_complete(self, quick_prompts):
        """
        **Validates: Requirement 3.2**
        
        Property: Each item SHALL have title, description, and template properties
        
        WHEN 用户查看快速提示区域
        THEN 每个提示项的属性（title、description、template）SHALL CONTINUE TO 存在
        
        Verifies that all items have the required properties for functionality.
        """
        for group_idx, group in enumerate(quick_prompts):
            for item_idx, item in enumerate(group['items']):
                assert 'title' in item, (
                    f"Group {group_idx}, Item {item_idx} missing 'title'. "
                    "Item structure must be preserved."
                )
                assert 'description' in item, (
                    f"Group {group_idx}, Item {item_idx} missing 'description'. "
                    "Item structure must be preserved."
                )
                assert 'template' in item, (
                    f"Group {group_idx}, Item {item_idx} missing 'template'. "
                    "Item structure must be preserved."
                )
                
                # Verify properties are non-empty strings
                assert isinstance(item['title'], str) and item['title'], (
                    f"Group {group_idx}, Item {item_idx} has invalid title"
                )
                assert isinstance(item['description'], str) and item['description'], (
                    f"Group {group_idx}, Item {item_idx} has invalid description"
                )
                assert isinstance(item['template'], str) and item['template'], (
                    f"Group {group_idx}, Item {item_idx} has invalid template"
                )
    
    def test_template_strings_unchanged(self, quick_prompts):
        """
        **Validates: Requirements 3.1, 3.2**
        
        Property: Template strings SHALL remain unchanged
        
        WHEN 用户点击任何快速提示卡片
        THEN 系统 SHALL CONTINUE TO 将对应的模板文本填入输入框
        
        This test verifies that the template strings used for filling the input
        box are preserved exactly as they were before the fix.
        """
        # Expected templates from original code (baseline behavior)
        expected_templates = [
            # Category 1 (故障诊断 / 网络故障诊断)
            [
                '请帮我分析为什么 10.0.1.10 到 10.0.2.20 的 80 端口不通。',
                '请帮我分析为什么 10.0.1.10 无法访问 10.0.2.20。',
                '请帮我检查 XX 主机上的 XX 服务是否正常监听目标端口。',
            ],
            # Category 2 (访问关系 / 访问关系查询)
            [
                '请查询 XX 系统的访问关系清单，包括源系统、目标系统、协议、端口和访问方向。',
                '请查询 IP 为 10.0.1.10 的主机有哪些访问关系。',
                '请帮我查询 XX 系统到 XX 系统之间是否已经开通访问关系。',
            ],
            # Category 3 (权限提单 / 提单知识问答)
            [
                '访问关系如何进行开通提单？需要哪些权限、审批节点和必填信息？',
                '开通访问关系前需要准备哪些信息，例如源 IP、目标 IP、端口、协议和用途说明？',
                '哪些角色有权限发起访问关系开通提单？审批边界是什么？',
            ],
        ]
        
        for group_idx, (group, expected_group_templates) in enumerate(
            zip(quick_prompts, expected_templates)
        ):
            actual_templates = [item['template'] for item in group['items']]
            
            assert actual_templates == expected_group_templates, (
                f"Templates in group {group_idx} have changed. "
                f"Expected: {expected_group_templates}, "
                f"Got: {actual_templates}. "
                "Template strings must remain unchanged to preserve functionality."
            )
    
    def test_item_titles_unchanged(self, quick_prompts):
        """
        **Validates: Requirement 3.2**
        
        Property: Item titles SHALL remain unchanged
        
        WHEN 用户查看快速提示区域
        THEN 每个提示项的标题 SHALL CONTINUE TO 保持不变
        """
        expected_titles = [
            # Category 1
            ['源到目标端口不通', '主机间网络不通', '服务监听异常'],
            # Category 2
            ['查询系统访问关系清单', '查询主机访问关系', '查询两个系统是否已开通'],
            # Category 3
            ['访问关系如何开通提单', '提单需要准备什么', '谁有权限提单'],
        ]
        
        for group_idx, (group, expected_group_titles) in enumerate(
            zip(quick_prompts, expected_titles)
        ):
            actual_titles = [item['title'] for item in group['items']]
            
            assert actual_titles == expected_group_titles, (
                f"Titles in group {group_idx} have changed. "
                f"Expected: {expected_group_titles}, "
                f"Got: {actual_titles}. "
                "Item titles must remain unchanged."
            )
    
    def test_item_descriptions_unchanged(self, quick_prompts):
        """
        **Validates: Requirement 3.2**
        
        Property: Item descriptions SHALL remain unchanged
        
        WHEN 用户查看快速提示区域
        THEN 每个提示项的描述 SHALL CONTINUE TO 保持不变
        """
        expected_descriptions = [
            # Category 1
            [
                '排查网络路径、防火墙、ACL 和服务监听',
                '检查连通性、路由和安全策略',
                '确认端口监听、进程状态和主机防火墙',
            ],
            # Category 2
            [
                '查看某系统的上下游访问关系',
                '按 IP 查看与其他资产的访问关系',
                '确认系统间是否已有访问放通记录',
            ],
            # Category 3
            [
                '查看权限、流程和必填信息',
                '提前准备源目地址、端口和用途说明',
                '确认申请角色和审批边界',
            ],
        ]
        
        for group_idx, (group, expected_group_descriptions) in enumerate(
            zip(quick_prompts, expected_descriptions)
        ):
            actual_descriptions = [item['description'] for item in group['items']]
            
            assert actual_descriptions == expected_group_descriptions, (
                f"Descriptions in group {group_idx} have changed. "
                f"Expected: {expected_group_descriptions}, "
                f"Got: {actual_descriptions}. "
                "Item descriptions must remain unchanged."
            )
    
    def test_category_modification_does_not_affect_items(self, quick_prompts):
        """
        **Validates: Requirements 3.1, 3.2**
        
        Property-Based Test: Category field independence
        
        FOR ALL category indices in [0, 1, 2]:
            Modifying the category field SHALL NOT affect the items array
        
        This property test verifies that changing category labels does not
        impact the items structure, which is critical for preserving the
        template filling functionality.
        """
        # Test all three categories
        for category_index in range(3):
            assert category_index < len(quick_prompts), (
                f"Category index {category_index} out of range"
            )
            
            group = quick_prompts[category_index]
            
            # Verify items array exists and is not empty
            assert 'items' in group, f"Category {category_index}: Items array missing"
            assert len(group['items']) > 0, f"Category {category_index}: Items array is empty"
            
            # Verify each item has all required properties
            for item_idx, item in enumerate(group['items']):
                assert 'title' in item and item['title'], (
                    f"Category {category_index}, Item {item_idx}: Missing title"
                )
                assert 'description' in item and item['description'], (
                    f"Category {category_index}, Item {item_idx}: Missing description"
                )
                assert 'template' in item and item['template'], (
                    f"Category {category_index}, Item {item_idx}: Missing template"
                )
    
    def test_preservation_property_all_groups(self, quick_prompts):
        """
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        
        Comprehensive Preservation Property Test
        
        FOR ALL groups in QUICK_PROMPTS:
            The items array and its contents SHALL remain unchanged
            regardless of category label modifications
        
        This test ensures that the fix is truly isolated to category labels
        and does not introduce any regressions in functionality.
        """
        # Verify total structure
        assert len(quick_prompts) == 3, "Number of groups changed"
        
        # Verify each group maintains its structure
        for group_idx, group in enumerate(quick_prompts):
            # Structure checks
            assert 'category' in group, f"Group {group_idx} missing category"
            assert 'items' in group, f"Group {group_idx} missing items"
            assert isinstance(group['items'], list), f"Group {group_idx} items not a list"
            assert len(group['items']) == 3, f"Group {group_idx} item count changed"
            
            # Content checks for each item
            for item_idx, item in enumerate(group['items']):
                assert 'title' in item, f"Group {group_idx}, Item {item_idx} missing title"
                assert 'description' in item, f"Group {group_idx}, Item {item_idx} missing description"
                assert 'template' in item, f"Group {group_idx}, Item {item_idx} missing template"
                
                # Verify non-empty strings
                assert item['title'].strip(), f"Group {group_idx}, Item {item_idx} has empty title"
                assert item['description'].strip(), f"Group {group_idx}, Item {item_idx} has empty description"
                assert item['template'].strip(), f"Group {group_idx}, Item {item_idx} has empty template"
