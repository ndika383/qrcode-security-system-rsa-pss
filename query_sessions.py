import sqlite3, json

conn = sqlite3.connect('data/testing/testing_results.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get all sessions
c.execute('SELECT * FROM test_sessions ORDER BY start_time')
sessions = c.fetchall()

print('='*80)
print('DATA SEMUA SESI PENGUJIAN - RECENT TEST SESSIONS')
print('='*80)
print('\nTotal Sesi: {}\n'.format(len(sessions)))

# Group by test type
summary = {}
for s in sessions:
    t = s['test_type']
    if t not in summary:
        summary[t] = {'completed': 0, 'stopped': 0, 'failed': 0, 'total_ops': 0, 'completed_ops': 0}
    status = s['status']
    summary[t][status] = summary[t].get(status, 0) + 1
    summary[t]['total_ops'] += s['total_operations']
    summary[t]['completed_ops'] += (s['completed_operations'] or 0)

print('RINGKASAN PER SKENARIO:')
print('-'*80)
for t, data in summary.items():
    print('\n{}:'.format(t.upper()))
    print('  Sesi Selesai   : {}'.format(data.get('completed', 0)))
    print('  Sesi Dihentikan: {}'.format(data.get('stopped', 0)))
    print('  Sesi Gagal     : {}'.format(data.get('failed', 0)))
    print('  Total Operasi  : {:,}'.format(data['total_ops']))
    print('  Operasi Selesai: {:,}'.format(data['completed_ops']))

print('\n' + '='*80)
print('TOTAL KESELURUHAN:')
print('  Total Sesi          : {}'.format(len(sessions)))
print('  Total Operasi       : {:,}'.format(sum(s['total_operations'] for s in sessions)))
print('  Operasi Selesai     : {:,}'.format(sum(s['completed_operations'] or 0 for s in sessions)))
print('='*80)

conn.close()
