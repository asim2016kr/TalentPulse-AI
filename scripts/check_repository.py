"""Check the Git index for accidental credentials/artifacts; never print matches."""
import re
import subprocess
import sys

def main():
    names = subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
    patterns = [
        rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        rb'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}',
        rb'\bAIza[0-9A-Za-z_-]{35}',
        rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}',
        rb'postgres(?:ql)?://[^\s/:]+:([^\s@]+)@',
    ]
    failures=[]
    for name in filter(None,names):
        parts=name.split('/')
        if (any(p in {'node_modules','.next','venv','output','__pycache__'} for p in parts)
            or (parts[-1].startswith('.env') and parts[-1]!='.env.example')):
            failures.append(name+': private/generated artifact');continue
        content=subprocess.check_output(['git','show',':'+name])
        for pattern in patterns:
            for match in re.finditer(pattern,content):
                # Documentation uses explicit uppercase placeholders only.
                value=match.group(1) if match.lastindex else match.group()
                if match.lastindex and (b'YOUR_' in value or value in {b'password',b'PASSWORD'}):continue
                failures.append(name+': potential credential');break
    if failures:
        print('\n'.join(sorted(set(failures))));return 1
    print('Repository credential/artifact checks passed.');return 0

if __name__=='__main__':sys.exit(main())
