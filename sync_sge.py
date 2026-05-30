import os
import re
import io
import requests
from bs4 import BeautifulSoup
import pdfplumber
import urllib3
from datetime import datetime, date
from urllib.parse import urljoin
from notion_utils import push_to_notion_v2

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SILVER_DB = "2bc47eb5fd3c80f3a71ad8de149a4943"

def fetch_latest_sge_pdf():
    url = "https://www.sge.com.cn/sjzx/hqzb"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"[*] Discovering SGE PDF lists from: {url}")
    r = requests.get(url, headers=headers, verify=False, timeout=15)
    r.raise_for_status()
    
    soup = BeautifulSoup(r.text, 'html.parser')
    pdf_entries = []
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.lower().endswith('.pdf'):
            title = a.get_text(strip=True)
            m = re.search(r'(\d{8})-(\d{8})周报', title)
            if m:
                start, end = m.group(1), m.group(2)
                pdf_entries.append({
                    "title": title,
                    "url": urljoin("https://www.sge.com.cn", href),
                    "week_end": datetime.strptime(end, "%Y%m%d").date(),
                })

    # 去重
    unique_entries = {}
    for entry in pdf_entries:
        if entry["url"] not in unique_entries:
            unique_entries[entry["url"]] = entry
            
    # 按时间降序
    sorted_entries = sorted(
        unique_entries.values(),
        key=lambda x: x["week_end"],
        reverse=True
    )
    
    if not sorted_entries:
        raise RuntimeError("【强制拦截】未能从 SGE /sjzx/hqzb 页面找到任何匹配周报格式的 PDF 链接。")
        
    return sorted_entries[0]

def parse_sge_silver_pdf(pdf_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    r = requests.get(pdf_url, headers=headers, verify=False, timeout=30)
    r.raise_for_status()
    
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        full_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        
    silver_match = re.search(r'白银\s+([\d,]+\.?\d*)\s+([+-]?[\d,]+\.?\d*)\s+([\d,]+\.?\d*)', full_text)
    if not silver_match:
        snippet = full_text[:800]
        raise ValueError(f"无法在 PDF 中找到白银库存正则匹配。PDF 文本前 800 字:\n{snippet}")
        
    try:
        this_week_kg = float(silver_match.group(3).replace(",", ""))
        this_week_tons = this_week_kg / 1000.0
        return this_week_tons
    except Exception as e:
        raise ValueError(f"解析白银数据行 '{silver_match.group(0)}' 失败: {e}")

def sync_sge_inventory():
    print("🔄 Discovering SGE PDF...")
    try:
        latest_entry = fetch_latest_sge_pdf()
        week_end_str = latest_entry["week_end"].isoformat()
        pdf_url = latest_entry["url"]
        
        print(f"📥 Found latest report: {latest_entry['title']} ({week_end_str})")
        
        # 解析白银库存
        sh_tons = parse_sge_silver_pdf(pdf_url)
        print(f"✅ SGE 白银周库存: {sh_tons} 吨 (报告期末: {week_end_str})")
        
        push_to_notion_v2(
            metal="Silver",
            db_id=SILVER_DB,
            market="SGE",
            date_str=week_end_str,
            freq="每周",
            sh_tons=sh_tons,
            source_url=pdf_url,
            note=f"SGE 白银周库存 / akshare 无此接口 / PDF 来源"
        )
    except Exception as e:
        # Fail Loud: 打印全部堆栈，不静默跳过
        print(f"❌ SGE 同步遭遇错误: {e}")
        raise e

if __name__ == "__main__":
    sync_sge_inventory()
