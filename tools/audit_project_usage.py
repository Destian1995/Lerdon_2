"""Conservative, read-only inventory of imports and data-driven asset paths.

Absence from this report's references is a review candidate, never permission
to delete: f-strings, directory enumeration and saved games can supply paths.
"""
import ast
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3

ROOT=Path(__file__).resolve().parents[1]
SKIP={'.git','.release','.idea','.claude','__pycache__','.venv','.buildozer'}


def audit(root=ROOT):
    paths=[p for p in root.rglob('*') if p.is_file() and not any(s in SKIP for s in p.relative_to(root).parts)]
    production=[p for p in paths if p.suffix=='.py' and p.relative_to(root).parts[0] not in ('tools','tests','old')]
    modules={p.relative_to(root).with_suffix('').as_posix().replace('/','.').removesuffix('.__init__'):p for p in production}
    graph={key:set() for key in modules};texts={};constants=[]
    for p in paths:
        if p.suffix.lower() not in ('.py','.json','.atlas','.spec','.md','.sh','.txt'):continue
        text=p.read_text(encoding='utf-8-sig',errors='replace');texts[p.relative_to(root).as_posix()]=text
        if p.suffix!='.py':continue
        try:tree=ast.parse(text)
        except SyntaxError:continue
        constants.extend((node.value,p.relative_to(root).as_posix()) for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str))
        key=next((k for k,v in modules.items() if v==p),None)
        if key is None:continue
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):names=[n.name for n in node.names]
            elif isinstance(node,ast.ImportFrom):
                base=node.module or ''
                if node.level:
                    package=key.split('.') if p.name=='__init__.py' else key.split('.')[:-1]
                    if node.level>1:package=package[:-(node.level-1)]
                    base='.'.join(package+([base] if base else []))
                names=[base]+[base+'.'+n.name for n in node.names]
            elif isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value in modules:names=[node.value]
            else:continue
            graph[key].update(n for n in names if n in modules)
    reachable=set();todo=['main']
    while todo:
        name=todo.pop()
        if name in reachable:continue
        reachable.add(name);todo.extend(graph.get(name,()))
    database=[]
    for dbpath in paths:
        if dbpath.suffix not in ('.db','.sqlite3'):continue
        conn=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True)
        try:
            for table, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                quoted='"'+table.replace('"','""')+'"'
                for row in conn.execute('SELECT * FROM '+quoted):
                    for value in row:
                        if isinstance(value,str) and ('files' in value or 'assets' in value):database.append((value,'database:'+dbpath.name+':'+table))
        finally:conn.close()
    literals=[];families=[]
    for value,source in constants+database:
        value=value.replace('\\','/')
        for hit in re.finditer(r'(?:files|assets)/[^\s\x00\n\r\"\'<>]*',value):
            raw=hit.group(0).rstrip('.,;)')
            path=root/raw
            if path.is_file():literals.append((raw,source))
            elif path.is_dir() and raw not in ('files/','assets/'):families.append((raw.rstrip('/')+'/',source))
            else:
                # Incomplete f-string/path prefixes protect their directory.
                parent=raw.rsplit('/',1)[0] if '/' in raw else ''
                if parent not in ('files','assets') and (root/parent).is_dir():families.append((parent+'/',source))
    content='\n'.join(texts.values()).replace('\\','/')
    assets=[]
    for p in paths:
        relative=p.relative_to(root).as_posix()
        if p.relative_to(root).parts[0]!='files':continue
        sources=[src for path,src in literals if path==relative]
        if not sources and (relative in content or p.name in content):sources=['text-or-manifest-reference']
        if not sources:sources=[src for prefix,src in families if relative.startswith(prefix)]
        assets.append(dict(path=relative,bytes=p.stat().st_size,status='protected' if sources else 'review',sources=sorted(set(sources))))
    directories={}
    for p in paths:
        key=p.relative_to(root).parts[0] if len(p.relative_to(root).parts)>1 else '(root)'
        item=directories.setdefault(key,dict(files=0,bytes=0));item['files']+=1;item['bytes']+=p.stat().st_size
    return dict(entry='main',modules=len(modules),reachable=sorted(reachable),
        modules_outside_main_graph=sorted(set(modules)-reachable),
        imports={k:sorted(v) for k,v in sorted(graph.items())},directories=directories,
        assets=assets,asset_counts=dict(Counter(a['status'] for a in assets)),
        note='Review candidates can still be referenced by concatenation or existing saves; never auto-delete them.')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=audit();args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('modules','directories','modules_outside_main_graph','asset_counts')},ensure_ascii=False,indent=2))
