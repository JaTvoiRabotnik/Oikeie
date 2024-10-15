import sqlite3

def check_table_structure(db_path, table_name):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    result = cursor.fetchone()
    
    if result:
        print(f"Structure of '{table_name}' table:")
        print(result[0])
    else:
        print(f"Table '{table_name}' not found in the database.")
    
    conn.close()

if __name__ == "__main__":
    check_table_structure('instance/chat_app.db', 'member')
