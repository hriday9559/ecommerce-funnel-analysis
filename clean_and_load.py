import pandas as pd
import sqlite3
import os

def clean_and_load(csv_path='events.csv', db_path='ecommerce.db'):
    print('Reading events.csv...')
    df = pd.read_csv(csv_path)
    initial_len = len(df)
    
    # 1. Deduplication: Remove exact duplicate rows
    df_clean = df.drop_duplicates().copy()
    dropped_dups = initial_len - len(df_clean)
    
    # 2. Standardize timestamp: convert to ISO 8601 string YYYY-MM-DD HH:MM:SS
    df_clean['event_time'] = pd.to_datetime(df_clean['event_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # 3. Store into SQLite
    conn = sqlite3.connect(db_path)
    df_clean.to_sql('events', conn, index=False, if_exists='replace')
    
    # 4. Create Indexes
    cursor = conn.cursor()
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_session ON events(user_session);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_time ON events(event_time);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_cat ON events(category_code);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_session_product ON events(user_session, product_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_brand ON events(brand);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_product ON events(product_id);')
    conn.commit()
    conn.close()
    
    print(f'Successfully loaded {len(df_clean):,} clean records into {db_path} (dropped {dropped_dups:,} duplicates).')

if __name__ == '__main__':
    clean_and_load()
