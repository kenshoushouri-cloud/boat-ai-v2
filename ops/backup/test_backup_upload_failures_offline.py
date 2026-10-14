#!/usr/bin/env python3
"""Offline test of the real upload-stage logic using fake local file storage.

No real age, PostgreSQL, Railway, rclone, OAuth credentials or internet access.
The production Bash upload section is extracted rather than reimplemented.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

THIS = Path(__file__).resolve().parent
SOURCE = THIS / 'railway_pg_to_drive_stream.sh'
START_MARKER = 'stamp="$(date -u +%Y%m%dT%H%M%SZ)"'
HEADER = '''#!/usr/bin/env bash
set -euo pipefail
umask 077
fail() { printf 'BACKUP_ABORT=%s\\n' "$1" >&2; exit 1; }
target=v3
remote=boat-drive-v3
AGE_RECIPIENT=age1fixture
'''
PG_DUMP = '''#!/usr/bin/env bash
set -euo pipefail
printf 'mock-db-data-not-a-real-dump-12345678901234567890'
if [[ "${TEST_FAILURE:-}" == pg_fail ]]; then exit 83; fi
'''
AGE = '''#!/usr/bin/env python3
import os,sys
p=sys.stdin.buffer.read()
sys.stdout.buffer.write(b'MOCK_AGE_CIPHERTEXT_'+p)
if os.environ.get('TEST_FAILURE') == 'age_fail': sys.exit(84)
'''
RCLONE = '''#!/usr/bin/env python3
import os,sys,hashlib
from pathlib import Path
scenario=os.environ.get('TEST_FAILURE','success')
args=sys.argv[1:]
root=Path(os.environ['TEST_STORE'])
log=Path(os.environ['TEST_RCLONE_LOG'])
cmd=args[0]
with log.open('a') as f: f.write(cmd+' '+(' '.join(args[1:2]))+'\\n')
def file(remote):
    name=remote.split(':',1)[1]
    if not name or '/' in name or '..' in name: sys.exit(98)
    return root/name
if cmd=='rcat':
    dest=file(args[1]); data=sys.stdin.buffer.read()
    if (scenario=='rcat_fail' and dest.name.endswith('.dump.age.uploading')) or (scenario=='sidecar_fail' and dest.name.endswith('.sha256')) or (scenario=='ready_upload_fail' and dest.name.endswith('.ready.uploading')):
        dest.write_bytes(data[:max(1,len(data)//2)]); sys.exit(73)
    dest.write_bytes(data); sys.exit(0)
if cmd=='md5sum':
    if scenario=='md5_fail': sys.exit(74)
    path=file(args[1]); digest=hashlib.md5(path.read_bytes()).hexdigest()
    if scenario=='md5_bad': digest='0'*32
    print(digest+'  '+path.name); sys.exit(0)
if cmd=='moveto':
    if (scenario=='moveto_fail' and args[1].endswith('.dump.age.uploading')) or (scenario=='ready_promote_fail' and args[1].endswith('.ready.uploading')): sys.exit(75)
    file(args[1]).rename(file(args[2])); sys.exit(0)
if cmd=='lsf':
    if scenario=='lsf_fail': sys.exit(76)
    for p in sorted(root.iterdir()): print(p.name)
    sys.exit(0)
print('Unexpected fake rclone operation',cmd,file=sys.stderr)
sys.exit(97)
'''


class UploadFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.is_file():
            raise RuntimeError('Run next to the real railway_pg_to_drive_stream.sh')
        text=SOURCE.read_text()
        if text.count(START_MARKER)!=1 or 'BACKUP_UPLOAD_DONE' not in text:
            raise RuntimeError('Unexpected upload segment shape')
        cls.stage=HEADER+text[text.index(START_MARKER):]
        for needle in ('.uploading','tee "$tmpdir/hash-fifo"',
                       'remote_md5_mismatch; staging_not_promoted',
                       'checksum_upload_failed; staging_not_promoted',
                       'rclone moveto', 'ready_marker_upload_failed',
                       'BACKUP_UPLOAD_DONE'):
            if needle not in cls.stage: raise RuntimeError('Stage changed: '+needle)

    def run_scenario(self, scenario):
        with tempfile.TemporaryDirectory(prefix='boat-failure-mock-') as temp:
            root=Path(temp)
            bin_dir=root/'bin'; bin_dir.mkdir()
            store=root/'fake-drive';store.mkdir()
            for name,code in (('pg_dump',PG_DUMP),('age',AGE),('rclone',RCLONE)):
                p=bin_dir/name;p.write_text(code);p.chmod(0o700)
            entry=root/'stage.sh';entry.write_text(self.stage)
            env={**os.environ, 'PATH':str(bin_dir)+':'+os.environ.get('PATH','/usr/bin:/bin'),
                 'TEST_FAILURE':scenario,'TEST_STORE':str(store),
                 'TEST_RCLONE_LOG':str(root/'commands.log')}
            run=subprocess.run(['bash',str(entry)],env=env,capture_output=True,text=True,timeout=15)
            names=[p.name for p in store.iterdir()]
            operations=(root/'commands.log').read_text().splitlines() if (root/'commands.log').exists() else []
            promoted=[n for n in names if n.endswith('.dump.age')]
            checksum=[n for n in names if n.endswith('.dump.age.sha256')]
            ready=[n for n in names if n.endswith('.dump.age.ready')]
            if scenario=='success':
                self.assertEqual(run.returncode,0,(run.stdout,run.stderr))
                self.assertIn('BACKUP_UPLOAD_DONE',run.stdout)
                self.assertEqual(len(promoted),1)
                self.assertEqual(len(checksum),1)
                self.assertEqual(len(ready),1)
                self.assertFalse(any(n.endswith('.uploading') for n in names))
                sha=hashlib.sha256((store/promoted[0]).read_bytes()).hexdigest()
                self.assertIn(sha,(store/checksum[0]).read_text())
                self.assertEqual((store/ready[0]).read_text(),(store/checksum[0]).read_text())
                self.assertIn('moveto ', '\n'.join(operations))
            else:
                self.assertNotEqual(run.returncode,0, (scenario,run.stdout,run.stderr))
                self.assertNotIn('BACKUP_UPLOAD_DONE',run.stdout)
                if scenario !='lsf_fail' and not scenario.startswith('ready_'):
                    self.assertEqual(promoted,[],(scenario,names))
                if scenario in {'pg_fail','age_fail','rcat_fail','md5_fail','md5_bad','sidecar_fail'}:
                    self.assertFalse(any(line.startswith('moveto ') for line in operations),operations)
                if scenario in ('lsf_fail','ready_upload_fail','ready_promote_fail'):
                    self.assertEqual(ready,[])
                if scenario=='lsf_fail':
                    # Promotion may have succeeded; missing .ready prevents acceptance.
                    self.assertEqual(len(promoted),1)
            print(f'PASS scenario={scenario} ret={run.returncode} files={len(names)}',flush=True)


for scenario in ['success','pg_fail','age_fail','rcat_fail','md5_fail','md5_bad',
                 'sidecar_fail','moveto_fail','lsf_fail','ready_upload_fail','ready_promote_fail']:
    setattr(UploadFailureTests,'test_'+scenario,lambda self,s=scenario:self.run_scenario(s))

if __name__=='__main__':
    unittest.main(verbosity=1)
