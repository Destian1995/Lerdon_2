"""p4a's AssetExtract expects a GZIP stream even though it is named private.tar."""
from pathlib import Path
import copy
import tarfile
from pathlib import PurePosixPath


def write_private_archive(source, destination, replacements):
    source,destination=Path(source),Path(destination)
    if source.resolve()==destination.resolve():
        raise ValueError('Source and destination archives must differ')
    with tarfile.open(source,'r:*') as old, tarfile.open(
            destination,'w:gz',format=tarfile.GNU_FORMAT,compresslevel=1) as new:
        directories=set()
        for member in old:
            name=member.name.removeprefix('./')
            if name in replacements or (name.endswith('.py') and name[:-3]+'.pyc' in replacements):
                continue
            entry=copy.copy(member)
            entry.pax_headers={}
            new.addfile(entry,old.extractfile(member) if member.isfile() else None)
            if member.isdir():
                directories.add(name.rstrip('/'))
        for name,path in replacements.items():
            if name.startswith('/') or '..' in Path(name).parts:
                raise ValueError('Invalid archive path')
            # Android's AssetExtract does not create a file's parent folders.
            for parent in reversed(PurePosixPath(name).parents):
                directory=str(parent)
                if directory=='.' or directory in directories:
                    continue
                entry=tarfile.TarInfo(directory)
                entry.type=tarfile.DIRTYPE;entry.mode=0o755
                new.addfile(entry);directories.add(directory)
            new.add(path,arcname=name,recursive=False)
