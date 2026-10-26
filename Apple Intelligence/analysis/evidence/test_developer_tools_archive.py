"""Archive regressions: distinct zero-inode XAR entries, checksums, PBZX/odc."""
import hashlib
import importlib.util
import lzma
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

spec = importlib.util.spec_from_file_location("archive_tools", Path(__file__).with_name("developer_tools_archive.py"))
archive_tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive_tools)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def xar(self, names=("first", "second"), corrupt=False):
        values = (b"first content", b"different second file")
        offset, entries = 20, []
        for name, value in zip(names, values):
            sha = hashlib.sha1(value).hexdigest()
            entries.append(f'<file><name>{name}</name><type>file</type><inode>0</inode>'
                           f'<data><offset>{offset}</offset><length>{len(value)}</length>'
                           f'<size>{len(value)}</size><encoding style="application/octet-stream"/>'
                           f'<archived-checksum style="sha1">{sha}</archived-checksum>'
                           f'<extracted-checksum style="sha1">{sha}</extracted-checksum></data></file>')
            offset += len(value)
        toc = ('<xar><toc><checksum style="sha1"><offset>0</offset><size>20</size></checksum>'
               + ''.join(entries) + '</toc></xar>').encode()
        packed = zlib.compress(toc)
        data = struct.pack('>4sHHQQI', b'xar!', 28, 1, len(packed), len(toc), 1)
        data += packed + hashlib.sha1(packed).digest() + b''.join(values)
        if corrupt:
            data = data[:-1] + bytes([data[-1] ^ 1])
        source = self.root / 'sample.pkg'
        source.write_bytes(data)
        return source, values

    def test_unrelated_inode_zero_files_remain_distinct(self):
        source, values = self.xar()
        out = self.root / 'output'
        report = archive_tools.extract_xar(source, out)
        self.assertEqual([(out / name).read_bytes() for name in ('first', 'second')], list(values))
        self.assertNotEqual((out / 'first').stat().st_ino, (out / 'second').stat().st_ino)
        self.assertTrue(all(f['archive_checksums_verified'] for f in report['files']))

    def test_corrupt_xar_payload_rejected(self):
        source, _ = self.xar(corrupt=True)
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            archive_tools.extract_xar(source, self.root / 'output')

    def test_parent_path_rejected(self):
        source, _ = self.xar(names=('..', 'second'))
        with self.assertRaisesRegex(ValueError, 'unsafe XAR'):
            archive_tools.extract_xar(source, self.root / 'output')

    def test_pbzx_compressed_and_raw_chunks(self):
        compressed = lzma.compress(b'first compressed chunk')
        raw = b'last raw chunk'
        source = self.root / 'Payload'
        source.write_bytes(b'pbzx' + struct.pack('>Q', 0x1000000)
                           + struct.pack('>QQ', 0x1000000, len(compressed)) + compressed
                           + struct.pack('>QQ', 0, len(raw)) + raw)
        target = self.root / 'data'
        result = archive_tools.unpack_pbzx(source, target)
        self.assertEqual(target.read_bytes(), b'first compressed chunk' + raw)
        self.assertEqual([c['encoding'] for c in result['chunks']], ['xz', 'raw'])

    def test_truncated_pbzx_rejected(self):
        source = self.root / 'Payload'
        source.write_bytes(b'pbzx' + struct.pack('>Q', 0x1000000)
                           + struct.pack('>QQ', 0, 100) + b'truncated')
        with self.assertRaisesRegex(ValueError, 'truncated archive'):
            archive_tools.unpack_pbzx(source, self.root / 'data')

    def test_unaligned_odc_inventory(self):
        def entry(name, data):
            name = name.encode() + b'\0'
            header = b'070707' + b'000000' * 2 + b'100644' + b'000000' * 4
            header += b'00000000000' + f'{len(name):06o}{len(data):011o}'.encode()
            return header + name + data
        source = self.root / 'sample.cpio'
        source.write_bytes(entry('./first', b'abc') + entry('./second', b'xyz12')
                           + entry('TRAILER!!!', b''))
        result = archive_tools.inventory_cpio(source)['entries']
        self.assertEqual([r['size'] for r in result], [3, 5])
        with source.open('rb') as stream:
            for record, expected in zip(result, (b'abc', b'xyz12')):
                stream.seek(record['data_offset'])
                self.assertEqual(stream.read(record['size']), expected)
                self.assertEqual(record['sha256'], hashlib.sha256(expected).hexdigest())


if __name__ == '__main__':
    unittest.main()
