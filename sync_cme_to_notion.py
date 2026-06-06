import os
import re
import time
import requests
import xlrd
import sys
from datetime import datetime
from notion_client import Client
from notion_utils import push_to_notion_v2
from sync_sge import sync_sge_inventory


# ---------------- 配置区 ----------------
GITHUB_REPO = "Curarpikt0000/cme-data-archive" 
GITHUB_TOKEN = os.getenv("GH_PERSONAL_TOKEN") or os.getenv("GITHUB_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
notion = Client(auth=NOTION_TOKEN)

SYNC_MODE = "latest" 

CONFIG = {
    "Gold": {
        "filename": "Gold_Stocks.xls",
        "db_id": "2bc47eb5fd3c8083966eecfd9f396b44",
        "reg_coords": (121, 7),  
        "elig_coords": (123, 7)  
    },
    "Silver": {
        "filename": "Silver_stocks.xls", 
        "db_id": "2bc47eb5fd3c80f3a71ad8de149a4943",
        "reg_coords": (72, 7),   
        "elig_coords": (73, 7)   
    },
    "Pt": {
        "filename": "PA-PL_Stck_Rprt.xls",
        "db_id": "2d647eb5fd3c801a9ce5d5db4d0b961a",
        "reg_coords": (71, 7),   
        "elig_coords": (72, 7)   
    }
}

def get_target_folders(repo, mode="latest"):
    api_url = f"https://api.github.com/repos/{repo}/contents/data"
    headers = {"Cache-Control": "no-cache", "Pragma": "no-cache"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
        
    response = requests.get(api_url, headers=headers)
    response.raise_for_status()
    
    all_dirs = [item['name'] for item in response.json() if item['type'] == 'dir']
    folder_items = [name for name in all_dirs if re.match(r'\d{4}-\d{2}-\d{2}', name)]
    
    if not folder_items:
        return []

    sorted_folders = sorted(folder_items, key=lambda x: datetime.strptime(x, "%Y-%m-%d"))
    
    if mode == "latest":
        return [sorted_folders[-1]]
    return sorted_folders

def parse_cme_excel(filepath, reg_coords, elig_coords):
    try:
        book = xlrd.open_workbook(filepath, ignore_workbook_corruption=True)
        sheet = book.sheet_by_index(0)
        activity_date = None
        for row_idx in range(min(150, sheet.nrows)):
            for col_idx in range(min(10, sheet.ncols)):
                cell_val = str(sheet.cell_value(row_idx, col_idx))
                if "Activity Date:" in cell_val:
                    match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', cell_val)
                    if match:
                        activity_date = datetime.strptime(match.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
                        break
            if activity_date: break
        reg_val = sheet.cell_value(reg_coords[0], reg_coords[1])
        elig_val = sheet.cell_value(elig_coords[0], elig_coords[1])
        return activity_date, float(reg_val), float(elig_val)
    except Exception as e:
        print(f"解析文件 {filepath} 失败: {e}")
        return None, 0, 0



def main():
    target_folders = get_target_folders(GITHUB_REPO, mode=SYNC_MODE)
    
    if not target_folders:
        print("❌ 未发现有效日期文件夹")
        sys.exit(1)
    
    for folder in target_folders:
        print(f"\n--- 正在处理日期: {folder} ---")
        for metal, config in CONFIG.items():
            filename = config["filename"]
            raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/data/{folder}/{filename}?t={int(time.time())}"
            
            try:
                r = requests.get(raw_url)
                if r.status_code != 200:
                    print(f"跳过: {metal} (404 Not Found at {folder})")
                    continue
                
                with open(filename, 'wb') as f:
                    f.write(r.content)
                
                date_str, reg_val, elig_val = parse_cme_excel(filename, config["reg_coords"], config["elig_coords"])
                
                if date_str:
                    push_to_notion_v2(metal, config["db_id"], "CME", date_str, "每日", reg=reg_val, elig=elig_val)
                time.sleep(0.5)
            except Exception as e:
                print(f"处理 {metal} 时出错: {e}")
                
    print("\n--- 正在处理 SGE 东方库存 ---")
    try:
        sync_sge_inventory()
    except Exception as e:
        print(f"处理 SGE 出错: {e}")

if __name__ == "__main__":
    main()
