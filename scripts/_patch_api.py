"""
用于向 api.py 追加访问关系资产 API 路由的辅助脚本
"""

NEW_CODE = """

# ===== 网络访问关系资产库 API =====

class AccessAssetCreate(BaseModel):
    \"\"\"新增网络访问关系资产请求\"\"\"
    src_system: str = Field(..., description="源物理子系统（代码）", min_length=1)
    src_system_name: str = Field(default="", description="源物理子系统中文名")
    src_deploy_unit: str = Field(default="", description="源部署单元属性")
    src_ip: str = Field(default="", description="源IP地址（多个用换行分隔）")
    dst_system: str = Field(..., description="目的物理子系统（代码）", min_length=1)
    dst_deploy_unit: str = Field(default="", description="目的部署单元属性")
    dst_ip: str = Field(default="", description="目的IP地址")
    protocol: str = Field(default="TCP", description="协议（TCP/UDP等）")
    port: str = Field(default="", description="目的端口（多个用换行分隔）")

    class Config:
        json_schema_extra = {
            "example": {
                "src_system": "N-AQM",
                "src_system_name": "金融资产质量管理",
                "src_deploy_unit": "AQMJS_AP",
                "src_ip": "10.37.1.116",
                "dst_system": "P-ZH-DMP-CONF",
                "dst_deploy_unit": "ADDNG_WB",
                "dst_ip": "10.87.28.127",
                "protocol": "TCP",
                "port": "8080"
            }
        }


@app.get("/api/v1/assets/access-relations")
async def list_access_assets(
    src_system: Optional[str] = None,
    dst_system: Optional[str] = None,
    keyword: Optional[str] = None,
    protocol: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    \"\"\"查询网络访问关系资产列表（支持多条件过滤+分页）\"\"\"
    try:
        if not hasattr(session_manager, 'db') or not session_manager.db:
            raise HTTPException(status_code=500, detail="数据库不可用")
        result = await session_manager.db.query_access_assets(
            src_system=src_system,
            dst_system=dst_system,
            keyword=keyword,
            protocol=protocol,
            page=max(1, page),
            page_size=min(100, max(1, page_size))
        )
        return {"status": "success", **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.post("/api/v1/assets/access-relations", status_code=201)
async def create_access_asset(request: AccessAssetCreate):
    \"\"\"新增一条网络访问关系资产记录\"\"\"
    try:
        if not hasattr(session_manager, 'db') or not session_manager.db:
            raise HTTPException(status_code=500, detail="数据库不可用")
        asset_id = await session_manager.db.create_access_asset(request.dict())
        if asset_id is None:
            raise HTTPException(status_code=500, detail="创建记录失败")
        return {"status": "success", "id": asset_id, "message": "访问关系记录已创建"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"新增失败: {str(e)}")


@app.delete("/api/v1/assets/access-relations/{asset_id}")
async def delete_access_asset_route(asset_id: int):
    \"\"\"删除一条网络访问关系资产记录\"\"\"
    try:
        if not hasattr(session_manager, 'db') or not session_manager.db:
            raise HTTPException(status_code=500, detail="数据库不可用")
        success = await session_manager.db.delete_access_asset(asset_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"记录不存在: {asset_id}")
        return {"status": "success", "message": "记录已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@app.get("/api/v1/assets/access-relations/chat-query")
async def chat_query_access_assets(keyword: str):
    \"\"\"
    聊天专用：按关键词查询访问关系，返回 Markdown 表格字符串

    ### 查询参数：
    - keyword: 搜索关键词（系统代码、中文名、IP等）
    \"\"\"
    try:
        if not keyword or not keyword.strip():
            raise HTTPException(status_code=400, detail="关键词不能为空")
        if not hasattr(session_manager, 'db') or not session_manager.db:
            raise HTTPException(status_code=500, detail="数据库不可用")
        result = await session_manager.db.query_access_assets(
            keyword=keyword.strip(), page=1, page_size=50
        )
        items = result.get("items", [])
        total = result.get("total", 0)
        if not items:
            return {
                "status": "success",
                "markdown": f"未找到与 **{keyword}** 相关的网络访问关系记录。",
                "total": 0
            }
        lines = [
            "| 源物理子系统 | 源系统名称 | 源部署单元 | 源IP地址 | 目的物理子系统 | 目的部署单元 | 目的IP | 协议 | 端口 |",
            "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|"
        ]
        for item in items:
            src_ip = (item.get("src_ip") or "").replace("\\n", " / ")
            port = (item.get("port") or "").replace("\\n", " / ")
            row = (
                f"| {item.get('src_system','')} "
                f"| {item.get('src_system_name','')} "
                f"| {item.get('src_deploy_unit','')} "
                f"| {src_ip} "
                f"| {item.get('dst_system','')} "
                f"| {item.get('dst_deploy_unit','')} "
                f"| {item.get('dst_ip','')} "
                f"| {item.get('protocol','TCP')} "
                f"| {port} |"
            )
            lines.append(row)
        markdown = f"找到 **{total}** 条与 **{keyword}** 相关的网络访问关系记录：\\n\\n" + "\\n".join(lines)
        return {"status": "success", "markdown": markdown, "total": total}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

"""

if __name__ == "__main__":
    api_path = "src/api.py"

    with open(api_path, "rb") as f:
        existing = f.read()

    # Remove the last `if __name__ == "__main__":` block
    marker = b'if __name__ == "__main__":'
    idx = existing.rfind(marker)
    if idx == -1:
        print("ERROR: could not find if __name__ marker")
        exit(1)

    base = existing[:idx]
    suffix = b'\nif __name__ == "__main__":\n    import uvicorn\n    uvicorn.run(app, host="0.0.0.0", port=8000)\n'

    final = base + NEW_CODE.encode("utf-8") + suffix

    with open(api_path, "wb") as f:
        f.write(final)

    print(f"Done! api.py updated, total {len(final)} bytes")
