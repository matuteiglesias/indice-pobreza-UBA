import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from poverty_pipeline.adapters import adapt_canastas_poverty_slice
from poverty_pipeline.contracts import ContractError

REGIONS = (
    "gran_buenos_aires",
    "cuyo",
    "noreste",
    "noroeste",
    "pampeana",
    "patagonia",
)
MONETARY_REFERENCE = (
    "research.argentina-price-consensus/curated-official-panel-v2@2016-01=100"
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CanastasBasketAdapterTests(unittest.TestCase):
    def release(self, root: Path, *, period: str = "2024-Q3") -> Path:
        rid = "poverty-baskets-v2-price-2024-q3-fixture"
        release = root / rid
        release.mkdir()
        table = release / "regional_baskets.csv"
        fields = [
            "period",
            "representative_date",
            "region_id",
            "CBA_2016_01",
            "CBT_2016_01",
            "unit",
            "monetary_reference_id",
            "status",
        ]
        with table.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for i, region in enumerate(REGIONS, start=1):
                writer.writerow(
                    {
                        "period": period,
                        "representative_date": "2024-08-15",
                        "region_id": region,
                        "CBA_2016_01": str(100 + i),
                        "CBT_2016_01": str(200 + i),
                        "unit": "ARS_per_equivalent_adult",
                        "monetary_reference_id": MONETARY_REFERENCE,
                        "status": "candidate",
                    }
                )
        manifest = {
            "schema": "research-artifact-manifest/v1",
            "artifact_type": "research.argentina-regional-baskets-poverty-input/v1",
            "release_id": rid,
            "status": "candidate",
            "method_id": (
                "research.argentina-regional-baskets/"
                "source-observed-plus-price-consensus-v2"
            ),
            "period": period,
            "regions": list(REGIONS),
            "unit": "ARS_per_equivalent_adult",
            "monetary_reference_id": MONETARY_REFERENCE,
            "scientific_poverty_execution_performed": False,
            "price_dependency": {
                "artifact_type": "research.argentina-monetary-conversion/v1",
                "release_id": "arg-monetary-conversion-v1-approved-fixture",
                "status": "approved",
                "manifest_sha256": "a" * 64,
            },
            "files": {
                table.name: {
                    "bytes": table.stat().st_size,
                    "sha256": sha(table),
                }
            },
        }
        (release / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return release

    def test_maps_exact_six_region_slice_to_poverty_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            release = self.release(Path(tmp))
            lines, qa = adapt_canastas_poverty_slice(
                release,
                poverty_method_release_id="research.poverty-method@v1",
                expected_period="2024-Q3",
            )
            self.assertEqual(lines.release_id, release.name)
            self.assertEqual(lines.period, "2024-Q3")
            self.assertEqual(lines.currency, "ARS")
            self.assertEqual(lines.price_reference, MONETARY_REFERENCE)
            self.assertEqual(len(lines.lines), 6)
            self.assertEqual(
                [line.threshold_area_id for line in lines.lines],
                list(REGIONS),
            )
            self.assertEqual(qa["source_release_id"], release.name)
            self.assertEqual(
                qa["price_dependency"]["status"],
                "approved",
            )
            self.assertFalse(qa["scientific_execution_performed"])

    def test_period_and_payload_hash_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            release = self.release(Path(tmp))
            with self.assertRaisesRegex(ContractError, "requested period"):
                adapt_canastas_poverty_slice(
                    release,
                    poverty_method_release_id="method@v1",
                    expected_period="2024-Q4",
                )
            with (release / "regional_baskets.csv").open(
                "a", encoding="utf-8"
            ) as stream:
                stream.write("\n")
            with self.assertRaisesRegex(ContractError, "payload identity"):
                adapt_canastas_poverty_slice(
                    release,
                    poverty_method_release_id="method@v1",
                )

    def test_duplicate_or_invalid_lines_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            release = self.release(Path(tmp))
            table = release / "regional_baskets.csv"
            with table.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            rows[-1]["region_id"] = rows[0]["region_id"]
            with table.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=list(rows[0]),
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerows(rows)
            manifest_path = release / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][table.name] = {
                "bytes": table.stat().st_size,
                "sha256": sha(table),
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            )
            with self.assertRaisesRegex(ContractError, "duplicate basket region"):
                adapt_canastas_poverty_slice(
                    release,
                    poverty_method_release_id="method@v1",
                )


if __name__ == "__main__":
    unittest.main()
