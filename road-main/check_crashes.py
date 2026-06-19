import pandas as pd
CRASH_COLS = ['crash_id','segment_id','severity','date','time','description']
try:
    crash_db = pd.read_csv('crash_database.csv')
except Exception as e:
    print('READ_ERROR:', e)
    crash_db = pd.DataFrame(columns=CRASH_COLS)
crash_db.columns = [c.lower().strip() for c in crash_db.columns]
for col in CRASH_COLS:
    if col not in crash_db.columns:
        crash_db[col] = None
crash_db = crash_db[CRASH_COLS]
print('SHAPE:', crash_db.shape)
print('COLUMNS:', crash_db.columns.tolist())
if len(crash_db):
    print('\nHEAD:')
    print(crash_db.head(10).to_string(index=False))
else:
    print('\nNo crash records present (empty dataframe).')
