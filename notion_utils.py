import os
from notion_client import Client

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
notion = Client(auth=NOTION_TOKEN)

def push_to_notion_v2(metal, db_id, market, date_str, freq, reg=None, elig=None, sh_tons=None, source_url=None, note=None):
    """
    General purpose Notion upsert for inventory rows.
    Uses (Date, Market) as deduplication key.
    """
    date_prop = f"{metal}日期"
    try:
        filter_data = {
            "and": [
                {"property": date_prop, "date": {"equals": date_str}},
                {"property": "市场", "select": {"equals": market}}
            ]
        }
        
        if hasattr(notion, 'data_sources'):
            db_info = notion.databases.retrieve(database_id=db_id)
            assert db_info is not None, f"无法检索到数据库元数据: {db_id}"
            
            if "data_sources" in db_info and len(db_info["data_sources"]) > 0:
                ds_id = db_info["data_sources"][0]["id"]
                exists_check = notion.data_sources.query(
                    data_source_id=ds_id,
                    filter=filter_data
                ).get("results")
            else:
                raise RuntimeError("db_info 缺 data_sources 字段——异常情况,需人工介入")
        else:
            exists_check = notion.databases.query(
                database_id=db_id,
                filter=filter_data
            ).get("results")
            
        assert exists_check is not None, "去重查询返回了 None 结果"
        assert isinstance(exists_check, list), f"去重查询返回了非列表结果: {type(exists_check)}"
        exists = exists_check
        
    except Exception as e:
        raise RuntimeError(f"[{metal}] [{market}] 执行去重查询时出错，可能存在 Notion 权限或 API 路径配置问题，已强制 Fail Loud 拦截: {e}")

    if exists:
        print(f"[{metal}] [{market}] 跳过: {date_str} 数据已存在")
        return

    name_content = f"{metal} {date_str}" if market == "CME" else f"{metal} {market} {date_str}"
    
    properties = {
        "Name": {"title": [{"text": {"content": name_content}}]},
        date_prop: {"date": {"start": date_str}},
        "市场": {"select": {"name": market}},
        "库存频率": {"select": {"name": freq}}
    }
    
    if reg is not None:
        properties[f"{metal} Reg库存"] = {"number": reg}
    if elig is not None:
        properties[f"{metal} Elig库存"] = {"number": elig}
    if sh_tons is not None:
        properties["SH库存吨"] = {"number": sh_tons}
    if source_url:
        properties["URL"] = {"url": source_url}
    if note:
        properties["说明"] = {"rich_text": [{"text": {"content": note}}]}
        
    try:
        notion.pages.create(
            parent={"database_id": db_id},
            properties=properties
        )
        print(f"[{metal}] [{market}] 成功同步: {date_str}")
    except Exception as e:
        print(f"[{metal}] [{market}] 写入 Notion 失败: {e}")
