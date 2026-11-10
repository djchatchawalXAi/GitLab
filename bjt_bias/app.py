"""Flask application factory for the BJT common-emitter bias calculator."""

from flask import Flask, render_template, request

from bias import Region, ValidationError, analyze, parse_input

FIELD_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("vcc", "VCC", "V", "12"),
    ("r1", "R1", "kΩ", "47"),
    ("r2", "R2", "kΩ", "10"),
    ("rc", "RC", "kΩ", "2.2"),
    ("re", "RE", "kΩ", "0.47"),
    ("beta", "β", "—", "150"),
    ("vbe", "VBE", "V", "0.7"),
)

FIELD_DEFAULTS: dict[str, str] = {
    name: default for name, _label, _unit, default in FIELD_SPECS
}

REGION_LABELS: dict[Region, str] = {
    Region.CUTOFF: "Cut-off",
    Region.SATURATION: "Saturation",
    Region.NEAR_SATURATION: "Near saturation",
    Region.FORWARD_ACTIVE: "Forward active",
}

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


def create_app() -> Flask:
    """Build the Flask application serving the bias calculator."""
    app = Flask(__name__)
    app.jinja_env.globals["format_quantity"] = format_quantity

    @app.get("/")
    def index():
        """Render the input form, prefilled or blank."""
        if request.args.get("blank") == "1":
            form = {name: "" for name, _label, _unit, _default in FIELD_SPECS}
        else:
            form = dict(FIELD_DEFAULTS)
        return render_template(
            "index.html",
            fields=FIELD_SPECS,
            form=form,
            errors={},
            analysis=None,
            region_labels=REGION_LABELS,
        )

    @app.post("/calculate")
    def calculate():
        """Validate the posted form and render results or field errors."""
        raw = request.form.to_dict()
        try:
            inp = parse_input(raw)
        except ValidationError as error:
            return render_template(
                "index.html",
                fields=FIELD_SPECS,
                form=raw,
                errors=error.errors,
                analysis=None,
                region_labels=REGION_LABELS,
            )
        return render_template(
            "index.html",
            fields=FIELD_SPECS,
            form=raw,
            errors={},
            analysis=analyze(inp),
            region_labels=REGION_LABELS,
        )

    return app


if __name__ == "__main__":
    create_app().run(debug=True, host="127.0.0.1", port=5000)
