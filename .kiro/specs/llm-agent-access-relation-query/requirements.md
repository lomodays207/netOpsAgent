# Requirements Document

## Introduction

本需求文档定义了为 LLM Agent（网络诊断 Agent）添加访问关系查询工具的功能需求。当前系统中，GeneralChatToolAgent 已经具备查询系统间访问关系的能力，但 LLMAgent 缺少此工具，导致在网络诊断场景中无法查询访问关系数据。本功能将为 LLMAgent 添加 `query_access_relations` 工具，使其能够在诊断网络连接问题时查询系统间的访问关系，从而提供更完整的诊断能力。

## Glossary

- **LLMAgent**: 网络故障诊断 Agent，位于 `src/agent/llm_agent.py`，使用 LangChain 框架动态决策并调用网络工具执行网络诊断
- **GeneralChatToolAgent**: 通用聊天 Agent，位于 `src/agent/general_chat_agent.py`，用于处理一般性对话和查询
- **query_access_relations**: 查询系统间访问关系的工具，可根据系统编码、系统名称、部署单元等条件查询访问关系数据
- **Access_Relation**: 访问关系记录，描述两个系统之间的网络访问关系，包括源系统、目标系统、协议、端口等信息
- **System_Code**: 系统编码，例如 N-CRM、N-OA，用于唯一标识一个应用系统
- **Deploy_Unit**: 部署单元，例如 CRMJS_AP、OAJS_WEB，表示系统的具体部署实例
- **Direction**: 查询方向，可选值为 outbound（该系统访问其他系统）、inbound（其他系统访问该系统）、both（双向关系）
- **Database_Module**: 数据库模块，位于 `src/db/database.py`，提供访问关系数据的查询方法
- **StructuredTool**: LangChain 框架中的结构化工具类，用于定义 Agent 可调用的工具
- **Tool_Input_Schema**: 工具输入参数的 Pydantic 模型，定义工具接受的参数类型和验证规则

## Requirements

### Requirement 1: 为 LLMAgent 添加访问关系查询工具

**User Story:** 作为网络诊断 Agent，我需要能够查询系统间的访问关系，以便在诊断网络连接问题时获取访问关系数据，从而提供更准确的诊断结果。

#### Acceptance Criteria

1. THE LLMAgent SHALL include a `query_access_relations` tool in its tool list
2. WHEN the `query_access_relations` tool is invoked, THE LLMAgent SHALL call the Database_Module query method with the provided parameters
3. WHEN the Database_Module returns query results, THE LLMAgent SHALL return the results to the caller in a structured format
4. THE `query_access_relations` tool SHALL accept optional parameters: system_code, system_name, deploy_unit, direction, peer_system_code, peer_system_name
5. THE `query_access_relations` tool SHALL use the same parameter schema as GeneralChatToolAgent for consistency

### Requirement 2: 定义工具输入参数模型

**User Story:** 作为开发者，我需要定义清晰的工具输入参数模型，以便 LLM 能够正确理解和使用访问关系查询工具。

#### Acceptance Criteria

1. THE LLMAgent SHALL define a Pydantic model named `QueryAccessRelationsInput` for tool input validation
2. THE `QueryAccessRelationsInput` model SHALL include fields: system_code, system_name, deploy_unit, direction, peer_system_code, peer_system_name
3. THE `QueryAccessRelationsInput` model SHALL mark all fields as optional except direction
4. THE direction field SHALL have a default value of "outbound"
5. THE `QueryAccessRelationsInput` model SHALL include field descriptions to guide LLM usage

### Requirement 3: 实现工具函数逻辑

**User Story:** 作为网络诊断 Agent，我需要工具函数能够正确查询访问关系数据，以便获取准确的系统间访问关系信息。

#### Acceptance Criteria

1. WHEN the tool function is invoked, THE LLMAgent SHALL check if the Database_Module is available
2. IF the Database_Module is not available, THEN THE LLMAgent SHALL return an error response indicating database unavailability
3. WHEN the Database_Module is available, THE LLMAgent SHALL invoke the `query_access_relations` method with the provided parameters
4. WHEN the database query completes, THE LLMAgent SHALL format the results into a structured response containing success status, data summary, query parameters, total count, and items
5. THE tool function SHALL limit query results to 50 items per invocation to prevent excessive data transfer

### Requirement 4: 集成工具到 LLMAgent 工具列表

**User Story:** 作为 LLMAgent，我需要将访问关系查询工具注册到我的工具列表中，以便 LLM 能够在诊断过程中调用此工具。

#### Acceptance Criteria

1. WHEN LLMAgent initializes, THE LLMAgent SHALL create a StructuredTool instance for `query_access_relations`
2. THE StructuredTool SHALL use the `QueryAccessRelationsInput` model as its args_schema
3. THE StructuredTool SHALL include a clear description explaining when to use this tool
4. WHEN the tool list is created, THE LLMAgent SHALL append the `query_access_relations` tool to the existing tool list
5. THE tool list SHALL contain execute_command, query_cmdb, ask_user, and query_access_relations tools after initialization

### Requirement 5: 处理数据库不可用场景

**User Story:** 作为网络诊断 Agent，我需要优雅地处理数据库不可用的情况，以便在数据库服务异常时仍能继续诊断流程。

#### Acceptance Criteria

1. WHEN the tool function is invoked, THE LLMAgent SHALL verify the session_manager has a valid db attribute
2. IF the session_manager is None, THEN THE LLMAgent SHALL return an error response with message "访问关系数据库不可用"
3. IF the session_manager.db is None, THEN THE LLMAgent SHALL return an error response with message "访问关系数据库不可用"
4. THE error response SHALL include success=False and error field with the error message
5. THE error response SHALL allow the LLM to continue diagnosis without crashing

### Requirement 6: 保持与 GeneralChatToolAgent 的一致性

**User Story:** 作为开发者，我需要确保 LLMAgent 的访问关系查询工具与 GeneralChatToolAgent 保持一致，以便维护代码的一致性和可维护性。

#### Acceptance Criteria

1. THE `QueryAccessRelationsInput` model in LLMAgent SHALL have the same field names and types as GeneralChatToolAgent
2. THE tool function signature in LLMAgent SHALL match the function signature in GeneralChatToolAgent
3. THE tool description in LLMAgent SHALL convey the same usage guidance as GeneralChatToolAgent
4. THE response format from LLMAgent SHALL match the response format from GeneralChatToolAgent
5. THE database query parameters passed by LLMAgent SHALL match those passed by GeneralChatToolAgent

### Requirement 7: 支持访问关系查询的多种场景

**User Story:** 作为网络诊断 Agent，我需要支持多种访问关系查询场景，以便满足不同的诊断需求。

#### Acceptance Criteria

1. WHEN only system_code is provided, THE LLMAgent SHALL query all access relations for that system
2. WHEN only system_name is provided, THE LLMAgent SHALL resolve the system_code and query access relations
3. WHEN deploy_unit is provided, THE LLMAgent SHALL filter access relations by deployment unit
4. WHEN direction is "outbound", THE LLMAgent SHALL query relations where the system is the source
5. WHEN direction is "inbound", THE LLMAgent SHALL query relations where the system is the target
6. WHEN direction is "both", THE LLMAgent SHALL query relations in both directions
7. WHEN peer_system_code or peer_system_name is provided, THE LLMAgent SHALL filter relations by the peer system

### Requirement 8: 提供清晰的工具使用指导

**User Story:** 作为 LLM，我需要清晰的工具描述和参数说明，以便在诊断过程中正确使用访问关系查询工具。

#### Acceptance Criteria

1. THE tool description SHALL explain the purpose of the query_access_relations tool
2. THE tool description SHALL indicate when to use this tool during network diagnosis
3. THE tool description SHALL explain the meaning of the direction parameter
4. THE parameter descriptions SHALL provide examples of valid input values
5. THE parameter descriptions SHALL clarify the difference between system_code and system_name

### Requirement 9: 确保工具函数的异步执行

**User Story:** 作为 LLMAgent，我需要工具函数支持异步执行，以便与现有的异步诊断流程保持一致。

#### Acceptance Criteria

1. THE tool function SHALL be defined as an async function
2. WHEN the Database_Module query method is invoked, THE LLMAgent SHALL use await to handle the asynchronous call
3. THE StructuredTool SHALL be created using the coroutine parameter to register the async function
4. THE tool function SHALL return results without blocking the event loop
5. THE tool function SHALL be compatible with the existing async diagnose method in LLMAgent

### Requirement 10: 验证工具集成的正确性

**User Story:** 作为开发者，我需要验证访问关系查询工具已正确集成到 LLMAgent 中，以便确保功能可用。

#### Acceptance Criteria

1. WHEN LLMAgent is instantiated, THE tools list SHALL contain exactly 4 tools
2. THE tools list SHALL include a tool with name "query_access_relations"
3. WHEN the tool is retrieved by name, THE tool SHALL have the correct args_schema
4. WHEN the tool is invoked with valid parameters, THE tool SHALL return a successful response
5. WHEN the tool is invoked with invalid parameters, THE tool SHALL raise a validation error
