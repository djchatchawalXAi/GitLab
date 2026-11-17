"""Flask application factory for the BJT common-emitter bias calculator."""

from collections.abc import Mapping
from dataclasses import dataclass

from flask import Flask, render_template, request

from bias import (CircuitType, DEFAULT_CIRCUIT, Region, ValidationError,
                  analyze, parse_input)

ALL_CIRCUITS = tuple(CircuitType)

CIRCUIT_LABELS = {
    CircuitType.VOLTAGE_DIVIDER: "Voltage Divider Bias",
    CircuitType.FIXED_BIAS: "Fixed Bias",
    CircuitType.EMITTER_BIAS: "Emitter Bias",
}

REGION_LABELS: dict[Region, str] = {
    Region.CUTOFF: "Cut-off",
    Region.SATURATION: "Saturation",
    Region.NEAR_SATURATION: "Near saturation",
    Region.FORWARD_ACTIVE: "Forward active",
}


def css_name(circuit: CircuitType) -> str:
    """Return the hyphenated CSS form of a circuit enum value."""
    return circuit.value.replace("_", "-")


@dataclass(frozen=True)
class FieldSpec:
    """One form field and the circuits that use it."""

    name: str
    label: str
    unit: str
    default: str
    circuits: tuple[CircuitType, ...]

    @property
    def css_class(self) -> str:
        if len(self.circuits) == len(ALL_CIRCUITS):
            return "for-all"
        return " ".join(f"for-{css_name(circuit)}" for circuit in self.circuits)


FIELD_SPECS = (
    FieldSpec("vcc", "VCC", "V", "12", ALL_CIRCUITS),
    FieldSpec("r1", "R1", "kΩ", "47", (CircuitType.VOLTAGE_DIVIDER,)),
    FieldSpec("r2", "R2", "kΩ", "10", (CircuitType.VOLTAGE_DIVIDER,)),
    FieldSpec("rb", "RB", "kΩ", "470", (CircuitType.FIXED_BIAS, CircuitType.EMITTER_BIAS)),
    FieldSpec("rc", "RC", "kΩ", "2.2", ALL_CIRCUITS),
    FieldSpec("re", "RE", "kΩ", "0.47", (CircuitType.VOLTAGE_DIVIDER, CircuitType.EMITTER_BIAS)),
    FieldSpec("beta", "β", "—", "150", ALL_CIRCUITS),
    FieldSpec("vbe", "VBE", "V", "0.7", ALL_CIRCUITS),
)
FIELD_DEFAULTS = {spec.name: spec.default for spec in FIELD_SPECS}

# Display scale and unit per quantity key; internal values are SI.
_QUANTITY_FORMATS: dict[str, tuple[float, str]] = {
    "ib": (1e6, "µA"),
    "ic": (1e3, "mA"),
    "ie": (1e3, "mA"),
    "vbb": (1.0, "V"),
    "vb": (1.0, "V"),
    "vc": (1.0, "V"),
    "ve": (1.0, "V"),
    "vce": (1.0, "V"),
    "rb": (1e-3, "kΩ"),
}


def format_quantity(value_si: float, key: str) -> str:
    """Return an SI quantity as a value in its display unit, with the unit."""
    scale, unit = _QUANTITY_FORMATS[key]
    return f"{value_si * scale:.4g} {unit}"


def resolve_circuit(value: str | None) -> CircuitType:
    """Resolve a query/form circuit value, falling back to the default."""
    try:
        return CircuitType((value or "").strip())
    except ValueError:
        return DEFAULT_CIRCUIT


def _form_values(raw: Mapping[str, str], *, blank: bool = False) -> dict[str, str]:
    """Return one value per field, preserving submitted text or using defaults."""
    return {spec.name: ("" if blank else raw.get(spec.name, spec.default))
            for spec in FIELD_SPECS}


def create_app() -> Flask:
    """Build the Flask application serving the bias calculator."""
    app = Flask(__name__)
    app.jinja_env.globals["format_quantity"] = format_quantity
    app.jinja_env.globals["css_name"] = css_name

    @app.get("/")
    def index():
        """Render the input form with the queried circuit selected."""
        circuit = resolve_circuit(request.args.get("circuit"))
        form = _form_values({}, blank=request.args.get("blank") == "1")
        form["circuit"] = circuit.value
        return render_template("index.html", fields=FIELD_SPECS, form=form,
                               errors={}, analysis=None,
                               region_labels=REGION_LABELS,
                               circuits=CIRCUIT_LABELS,
                               selected_circuit=circuit, result_circuit=None)

    @app.post("/calculate")
    def calculate():
        """Validate the posted form and render results or field errors."""
        raw = request.form.to_dict()
        try:
            inp = parse_input(raw)
        except ValidationError as error:
            circuit = resolve_circuit(raw.get("circuit"))
            form = _form_values(raw)
            form["circuit"] = circuit.value
            return render_template("index.html", fields=FIELD_SPECS, form=form,
                                   errors=error.errors, analysis=None,
                                   region_labels=REGION_LABELS,
                                   circuits=CIRCUIT_LABELS,
                                   selected_circuit=circuit,
                                   result_circuit=circuit)
        form = _form_values(raw)
        form["circuit"] = inp.circuit.value
        return render_template("index.html", fields=FIELD_SPECS, form=form,
                               errors={}, analysis=analyze(inp),
                               region_labels=REGION_LABELS,
                               circuits=CIRCUIT_LABELS,
                               selected_circuit=inp.circuit,
                               result_circuit=inp.circuit)

    return app


if __name__ == "__main__":
    create_app().run(debug=True, host="127.0.0.1", port=5000)
