import io
import json
import tempfile
import tarfile
import unittest
from pathlib import Path

from v4.catalog import Catalog, CatalogError, from_archive, blueprint_instance_kind


def archive(path, types, blueprints):
    with tarfile.open(path, "w:xz") as tar:
        for name,data in [("types.json", types),("blueprints.json",blueprints)]:
            buf=json.dumps(data).encode()
            entry=tarfile.TarInfo(name)
            entry.size=len(buf)
            tar.addfile(entry,io.BytesIO(buf))


class CatalogTests(unittest.TestCase):
    def test_real_contract_copy_and_original_signals(self):
        self.assertEqual(blueprint_instance_kind(True, 10), "BPC")
        self.assertEqual(blueprint_instance_kind(False, -1), "BPO")
        self.assertEqual(blueprint_instance_kind("true", 5.0), "BPC")
        self.assertEqual(blueprint_instance_kind("true", -1), "UNKNOWN_BLUEPRINT")
        self.assertEqual(blueprint_instance_kind(False, 10), "UNKNOWN_BLUEPRINT")
        self.assertEqual(blueprint_instance_kind(None, float("nan")), "UNKNOWN_BLUEPRINT")

    def test_bulk_type_volume_and_blueprint_classification(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"ref.tar.xz"
            archive(path,{
                "34":{"volume":0.01, "packaged_volume":0.01, "group_id":18},
                "39":{"volume":0.01, "packaged_volume":0, "groupID":86},
                "17477":{"volume":0.01, "packaged_volume":0.01, "group_id":726},
                "999":{"volume":0, "packaged_volume":None},
            },{"17477":{"blueprint_type_id":17477}})
            result=from_archive(path,min_types=1,min_blueprints=1)
            self.assertEqual(result.volume(34),0.01)
            self.assertEqual(result.volume(39),0.01)
            self.assertIsNone(result.volume(999))
            self.assertEqual(result.classification(17477),"blueprint_type")
            self.assertEqual(result.classification(34),"regular")
            self.assertEqual(result.classification(9999),"unknown")
            self.assertEqual(result.group_id(34),18)
            self.assertEqual(result.group_id(39),86)
            self.assertIsNone(result.group_id(999))
            self.assertIsNone(result.group_id(9999))
            self.assertEqual(result.coverage([34,39,17477,999,9999])["missing_volume"],2)
            result.save(Path(d)/"catalog.json.gz")
            reloaded=Catalog.load(Path(d)/"catalog.json.gz")
            self.assertEqual(reloaded.items,result.items)

    def test_invalid_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"ref.tar.xz"
            archive(path,{"34":{"volume":0.01}}, {})
            with self.assertRaises(CatalogError):
                from_archive(path,min_types=1,min_blueprints=1)

    def test_nonfinite_volume_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"ref.tar.xz"
            archive(path,{"17477":{"volume":float("nan")},
                          "34":{"volume":1, "packaged_volume":float("inf")}},
                    {"17477":{}})
            catalog=from_archive(path,min_types=1,min_blueprints=1)
            self.assertIsNone(catalog.volume(17477))
            self.assertEqual(catalog.volume(34),1)
