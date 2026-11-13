import gzip
import io
from pathlib import Path
from pathlib import PurePosixPath
import tarfile
import tempfile
import unittest
from tools.android_private_archive import write_private_archive


class PrivateArchiveTests(unittest.TestCase):
    def test_android_can_decompress_and_find_updated_entrypoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'old.tar';output=root/'private.tar'
            with tarfile.open(source,'w') as tar:
                for name,data in [('main.pyc',b'old'),('assets/game_data.db',b'clean-db')]:
                    entry=tarfile.TarInfo(name);entry.size=len(data)
                    tar.addfile(entry,io.BytesIO(data))
            compiled=root/'main.pyc';compiled.write_bytes(b'new-bytecode')
            write_private_archive(source,output,{'main.pyc':compiled})
            self.assertEqual(output.read_bytes()[:2],b'\x1f\x8b')
            with gzip.open(output,'rb') as gz,tarfile.open(fileobj=gz,mode='r|') as tar:
                files={m.name:tar.extractfile(m).read() for m in tar if m.isfile()}
            self.assertEqual(files,{'main.pyc':b'new-bytecode','assets/game_data.db':b'clean-db'})

    def test_new_package_directories_precede_files_for_android_extractor(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'old.tar';output=root/'private.tar'
            with tarfile.open(source,'w'):pass
            module=root/'module.pyc';module.write_bytes(b'bytecode')
            write_private_archive(source,output,{'certifi/cacert.pem':module,'utils/ui_text.pyc':module,
                                                'new/nested/__init__.pyc':module})
            directories={'.'}
            with tarfile.open(output,'r:gz') as tar:
                for entry in tar:
                    if entry.isdir():directories.add(entry.name.rstrip('/'))
                    else:self.assertIn(str(PurePosixPath(entry.name).parent),directories)


if __name__=='__main__':unittest.main()
