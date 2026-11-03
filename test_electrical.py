import unittest

from electrical import analyze_circuit, analyze_dc


class AnalyzeDcTests(unittest.TestCase):
    def test_calculates_current_and_power_for_single_resistor(self):
        self.assertEqual(analyze_dc(12, 6), {"current_a": 2, "power_w": 24})

    def test_rejects_zero_resistance(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            analyze_dc(12, 0)

    def test_allows_zero_voltage(self):
        self.assertEqual(analyze_dc(0, 6), {"current_a": 0, "power_w": 0})


class AnalyzeCircuitTests(unittest.TestCase):
    def test_calculates_series_circuit(self):
        result = analyze_circuit(12, "series(4, 8)")
        self.assertEqual(result["total_resistance_ohm"], 12)
        self.assertEqual(result["total_current_a"], 1)
        self.assertEqual(
            [(item["voltage_v"], item["current_a"]) for item in result["resistors"]],
            [(4, 1), (8, 1)],
        )

    def test_calculates_parallel_circuit(self):
        result = analyze_circuit(12, "parallel(6, 3)")
        self.assertEqual(result["total_resistance_ohm"], 2)
        self.assertEqual(result["total_current_a"], 6)
        self.assertEqual(
            [item["current_a"] for item in result["resistors"]],
            [2, 4],
        )

    def test_calculates_nested_mixed_circuit(self):
        result = analyze_circuit(22, "series(10, parallel(20, 30))")
        self.assertEqual(result["total_resistance_ohm"], 22)
        self.assertEqual(result["total_current_a"], 1)

        expected = [(10, 1), (12, 0.6), (12, 0.4)]
        for resistor, (voltage, current) in zip(result["resistors"], expected):
            self.assertAlmostEqual(resistor["voltage_v"], voltage)
            self.assertAlmostEqual(resistor["current_a"], current)

    def test_rejects_unsupported_circuit_expression(self):
        with self.assertRaisesRegex(ValueError, "Use positive resistance"):
            analyze_circuit(12, "invalid(4, 8)")

    def test_rejects_zero_resistance_in_circuit(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            analyze_circuit(12, "series(0, 8)")

    def test_zero_voltage_produces_zero_current_and_power(self):
        result = analyze_circuit(0, "series(4, 8)")
        self.assertEqual(result["total_current_a"], 0)
        self.assertEqual(result["total_power_w"], 0)


if __name__ == "__main__":
    unittest.main()
