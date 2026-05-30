import sqlite3
import os
import sys

# Add parent dir to path to import db_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def audit_local_db(db_path='ai_radio_dev.db'):
    if not os.path.exists(db_path):
        print(f"Local database {db_path} not found.")
        return

    print(f"Auditing Local Database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    fields_to_check = [
        'headline', 'source', 'topic_tags', 'my_take', 'post_text',
        'audio_script', 'audio_url', 'video_url', 'original_headline'
    ]

    cursor.execute("SELECT id, " + ", ".join(fields_to_check) + " FROM memory_log")
    rows = cursor.fetchall()

    if not rows:
        print("No records found in local database.")
        conn.close()
        return

    issues_found = 0
    for row in rows:
        row_id = row[0]
        issue_details = []
        for i, field in enumerate(fields_to_check):
            val = row[i+1]
            if val is None or val == "" or val == "[]" or val == "{}":
                issue_details.append(field)
        
        if issue_details:
            print(f"Row ID {row_id} has empty fields: {', '.join(issue_details)}")
            issues_found += 1

    print(f"Total rows audited: {len(rows)}")
    print(f"Rows with issues: {issues_found}")
    conn.close()

if __name__ == "__main__":
    audit_local_db()
