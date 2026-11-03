import ast
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Circuit:
    resistance_ohm: float | None = None
    connection: str | None = None
    components: tuple["Circuit", ...] = ()


def _positive_finite(value: float, name: str, *, allow_zero: bool = False) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be a number.")
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        qualifier = "non-negative" if allow_zero else "greater than zero"
        raise ValueError(f"{name} must be finite and {qualifier}.")


def _parse_circuit(expression: str) -> Circuit:
    try:
        syntax = ast.parse(expression, mode="eval").body
    except SyntaxError as error:
        raise ValueError("Enter a circuit such as series(10, parallel(20, 30)).") from error

    def parse(node: ast.expr) -> Circuit:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            _positive_finite(node.value, "Resistance")
            return Circuit(resistance_ohm=float(node.value))

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"series", "parallel"}
            and not node.keywords
            and len(node.args) >= 2
        ):
            return Circuit(
                connection=node.func.id,
                components=tuple(parse(component) for component in node.args),
            )

        raise ValueError(
            "Use positive resistance values and series(...) or parallel(...), "
            "with at least two components per group."
        )

    return parse(syntax)


def _equivalent_resistance(circuit: Circuit) -> float:
    if circuit.resistance_ohm is not None:
        return circuit.resistance_ohm

    resistances = [_equivalent_resistance(component) for component in circuit.components]
    if circuit.connection == "series":
        return sum(resistances)
    return 1 / sum(1 / resistance for resistance in resistances)


def analyze_dc(voltage_v: float, resistance_ohm: float) -> dict[str, float]:
    _positive_finite(voltage_v, "Voltage", allow_zero=True)
    _positive_finite(resistance_ohm, "Resistance")
    current_a = voltage_v / resistance_ohm
    return {"current_a": current_a, "power_w": voltage_v * current_a}


def analyze_circuit(voltage_v: float, expression: str) -> dict[str, object]:
    _positive_finite(voltage_v, "Voltage", allow_zero=True)
    circuit = _parse_circuit(expression)
    total_resistance = _equivalent_resistance(circuit)
    total_current = voltage_v / total_resistance
    resistors: list[dict[str, float]] = []

    def distribute(node: Circuit, node_voltage: float, node_current: float) -> None:
        if node.resistance_ohm is not None:
            resistors.append(
                {
                    "resistance_ohm": node.resistance_ohm,
                    "voltage_v": node_voltage,
                    "current_a": node_current,
                    "power_w": node_voltage * node_current,
                }
            )
            return

        if node.connection == "series":
            for component in node.components:
                component_voltage = node_current * _equivalent_resistance(component)
                distribute(component, component_voltage, node_current)
        else:
            for component in node.components:
                component_current = node_voltage / _equivalent_resistance(component)
                distribute(component, node_voltage, component_current)

    distribute(circuit, voltage_v, total_current)
    return {
        "total_resistance_ohm": total_resistance,
        "total_current_a": total_current,
        "total_power_w": voltage_v * total_current,
        "resistors": resistors,
    }


def main() -> None:
    print("DC Circuit Calculator")
    voltage_v = float(input("Supply voltage (V): "))
    expression = input(
        "Circuit (e.g. series(10, parallel(20, 30))): "
    )
    result = analyze_circuit(voltage_v, expression)

    print(f"\nEquivalent resistance: {result['total_resistance_ohm']:.4g} ohm")
    print(f"Total current: {result['total_current_a']:.4g} A")
    print(f"Total power: {result['total_power_w']:.4g} W")
    for index, resistor in enumerate(result["resistors"], start=1):
        print(
            f"R{index} ({resistor['resistance_ohm']:.4g} ohm): "
            f"{resistor['voltage_v']:.4g} V, "
            f"{resistor['current_a']:.4g} A, "
            f"{resistor['power_w']:.4g} W"
        )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, ZeroDivisionError) as error:
        raise SystemExit(f"Error: {error}") from error
