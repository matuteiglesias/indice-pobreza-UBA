from dataclasses import replace
import unittest

from poverty_pipeline.contracts_v2 import (
    PopulationFrameHousehold,
    PopulationFramePerson,
    PopulationFrameRelease,
    PovertyLine,
    PovertyLineRelease,
    ThresholdAreaBinding,
    ThresholdAreaBindingRelease,
    V2ContractError,
    WelfareEstimate,
    WelfareRelease,
    prepare_measurement_inputs,
    validate_population_frame,
)
from poverty_pipeline.science import load_poverty_method, measure_poverty


METHOD_PATH = "configs/poverty_methods/indec-line-poverty-2016-v1.json"


def fixture_inputs():
    frame = PopulationFrameRelease(
        release_id="frame-fixture-v2",
        namespace="cpv2010:fixture-v2",
        frame_vintage="2010",
        sampling_design_id="deterministic-household-hash-v1",
        weight_semantics="cpv2010_frame_inverse_probability",
        persons=(
            PopulationFramePerson("p1", "h1", "male", 35, "020010101", "02001", "02"),
            PopulationFramePerson("p2", "h1", "female", 34, "020010101", "02001", "02"),
            PopulationFramePerson("p3", "h2", "female", 76, "020010102", "02001", "02"),
            PopulationFramePerson("p4", "h3", "male", 10, "060140101", "06014", "06"),
        ),
        households=(
            PopulationFrameHousehold("h1", "02001", "02", 0.10, 10.0),
            PopulationFrameHousehold("h2", "02001", "02", 0.20, 5.0),
            PopulationFrameHousehold("h3", "06014", "06", 0.25, 4.0),
        ),
    )
    welfare = WelfareRelease(
        release_id="welfare-fixture-v2",
        frame_namespace=frame.namespace,
        welfare_period="2024-Q1",
        currency="ARS",
        price_reference="2024-Q1-current",
        welfare_concept="household_total_family_income",
        estimates=(
            WelfareEstimate("h1", 260.0),
            WelfareEstimate("h2", 75.0),
            WelfareEstimate("h3", 100.0),
        ),
    )
    lines = PovertyLineRelease(
        release_id="lines-fixture-v2",
        period="2024-Q1",
        currency="ARS",
        price_reference="2024-Q1-current",
        method_release_id="argentina.indec-line-poverty-2016@v1",
        lines=(
            PovertyLine("gba", 100.0, 180.0),
            PovertyLine("pampeana", 90.0, 160.0),
        ),
    )
    binding = ThresholdAreaBindingRelease(
        release_id="threshold-binding-fixture-v2",
        geography_level="department_2010",
        bindings=(
            ThresholdAreaBinding("department_2010", "02001", "gba"),
            ThresholdAreaBinding("department_2010", "06014", "pampeana"),
        ),
    )
    return frame, welfare, lines, binding


class V2ContractsTest(unittest.TestCase):
    def setUp(self):
        self.method = load_poverty_method(METHOD_PATH)
        self.frame, self.welfare, self.lines, self.binding = fixture_inputs()

    def test_prepares_exact_p2_inputs_without_region_on_frame(self):
        prepared = prepare_measurement_inputs(
            self.frame, self.welfare, self.lines, self.binding, self.method,
            estimation_period="2024-Q1",
        )
        self.assertEqual({x.household_id for x in prepared.household_welfare}, {"h1", "h2", "h3"})
        measured = measure_poverty(
            prepared.persons, prepared.household_welfare, prepared.household_lines, self.method
        )
        self.assertEqual(len(measured.households), 3)
        self.assertEqual(len(measured.persons), 4)

    def test_frame_vintage_does_not_need_to_match_estimation_period(self):
        self.assertEqual(self.frame.frame_vintage, "2010")
        prepare_measurement_inputs(
            self.frame, self.welfare, self.lines, self.binding, self.method,
            estimation_period="2024-Q1",
        )

    def test_welfare_must_share_exact_frame_namespace(self):
        wrong = replace(self.welfare, frame_namespace="another-frame")
        with self.assertRaisesRegex(V2ContractError, "namespace mismatch"):
            prepare_measurement_inputs(
                self.frame, wrong, self.lines, self.binding, self.method,
                estimation_period="2024-Q1",
            )

    def test_line_release_pins_exact_method_release(self):
        wrong = replace(self.lines, method_release_id="argentina.indec-line-poverty-2016@v2")
        with self.assertRaisesRegex(V2ContractError, "exact poverty-method"):
            prepare_measurement_inputs(
                self.frame, self.welfare, wrong, self.binding, self.method,
                estimation_period="2024-Q1",
            )

    def test_monetary_reference_mismatch_fails_closed(self):
        wrong = replace(self.welfare, price_reference="2023-12-current")
        with self.assertRaisesRegex(V2ContractError, "monetary reference"):
            prepare_measurement_inputs(
                self.frame, wrong, self.lines, self.binding, self.method,
                estimation_period="2024-Q1",
            )

    def test_threshold_binding_is_separate_and_must_cover_frame(self):
        wrong = replace(self.binding, bindings=self.binding.bindings[:1])
        with self.assertRaisesRegex(V2ContractError, "exactly cover"):
            prepare_measurement_inputs(
                self.frame, self.welfare, self.lines, wrong, self.method,
                estimation_period="2024-Q1",
            )

    def test_person_household_geography_mismatch_fails(self):
        people = list(self.frame.persons)
        people[0] = replace(people[0], department_2010_id="99999")
        wrong = replace(self.frame, persons=tuple(people))
        with self.assertRaisesRegex(V2ContractError, "geography identity mismatch"):
            validate_population_frame(wrong)


if __name__ == "__main__":
    unittest.main()
