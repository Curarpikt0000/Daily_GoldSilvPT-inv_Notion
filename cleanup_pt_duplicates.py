import os
import sys
import argparse
from notion_client import Client

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DS_ID = "2d647eb5-fd3c-81ea-990a-000b045a931c"

if not NOTION_TOKEN:
    print("[-] Error: NOTION_TOKEN is not set in environment.")
    sys.exit(1)

notion = Client(auth=NOTION_TOKEN)

def cleanup_pt_duplicates(dry_run=True):
    print("[*] Retrieving all records from Pt Database...")
    all_pages = []
    cursor = None
    
    try:
        # Notion query pagination
        chunk_count = 0
        while True:
            chunk_count += 1
            kwargs = {
                "data_source_id": DS_ID,
                "page_size": 100
            }
            if cursor:
                kwargs["start_cursor"] = cursor
                
            res = notion.data_sources.query(**kwargs)
            results = res.get("results", [])
            all_pages.extend(results)
            print(f"    [Page {chunk_count}] Fetched {len(results)} pages. Total collected: {len(all_pages)}")
            
            if res.get("has_more") and res.get("next_cursor"):
                cursor = res.get("next_cursor")
            else:
                break
                
        # Group by date
        by_date = {}
        for page in all_pages:
            props = page.get("properties", {})
            date_val = None
            date_prop = props.get("Pt日期", {})
            if date_prop.get("type") == "date":
                date_data = date_prop.get("date")
                if date_data:
                    date_val = date_data.get("start")
                    
            if not date_val:
                continue
                
            by_date.setdefault(date_val, []).append({
                "id": page["id"],
                "created_time": page["created_time"]
            })
            
        print("\n[*] Starting duplicates analysis...")
        total_duplicates = 0
        total_archived = 0
        
        pending_archives = []
        
        for date_val, rows in sorted(by_date.items()):
            if len(rows) > 1:
                # Sort by created_time ascending (earliest first)
                sorted_rows = sorted(rows, key=lambda x: x["created_time"])
                
                # Keep the earliest page (index 0)
                keep_row = sorted_rows[0]
                delete_rows = sorted_rows[1:]
                
                print(f"[!] Date {date_val}: Total {len(rows)} rows. Keeping ID: {keep_row['id']} (Created: {keep_row['created_time']})")
                
                for r in delete_rows:
                    pending_archives.append({
                        "id": r["id"],
                        "date": date_val,
                        "created_time": r["created_time"]
                    })
                    total_duplicates += 1

        if dry_run:
            print("\n" + "="*80)
            print(" DRY RUN SUMMARY: PENDING ARCHIVE PAGES")
            print("="*80)
            print(f"{'Page ID':<38} | {'Pt日期':<12} | {'Created Time':<24}")
            print("-" * 80)
            for r in pending_archives:
                print(f"{r['id']:<38} | {r['date']:<12} | {r['created_time']:<24}")
            print("-" * 80)
            print(f"Total duplicates found: {total_duplicates} (No actions taken in dry-run mode).")
            print("="*80 + "\n")
        else:
            print(f"\n[*] Executing actual archive on {total_duplicates} pages...")
            for r in pending_archives:
                pid = r["id"]
                d = r["date"]
                ct = r["created_time"]
                try:
                    notion.pages.update(page_id=pid, archived=True)
                    print(f"[Archive] page_id={pid} date={d} created={ct}")
                    total_archived += 1
                except Exception as ex:
                    print(f"[-] Failed to archive page_id={pid} date={d}: {ex}")
            print(f"\n[+] Cleanup finished: Successfully archived {total_archived} duplicate pages.")
            
    except Exception as e:
        print(f"[-] Cleanup process failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup duplicate Pt records in Notion database.")
    parser.add_argument("--execute", action="store_true", help="Perform actual archive (defaults to dry-run)")
    args = parser.parse_args()
    
    dry_run = not args.execute
    if dry_run:
        print("[*] Running in DRY-RUN mode. No changes will be made to Notion.")
    else:
        print("[WARNING] Running in EXECUTE mode. Duplicate pages will be archived!")
        
    cleanup_pt_duplicates(dry_run=dry_run)
