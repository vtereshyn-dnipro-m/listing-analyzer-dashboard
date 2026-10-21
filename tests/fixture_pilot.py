# -*- coding: utf-8 -*-
"""
tests/fixture_pilot.py — не тест, а данные пяти пилотных товаров ES в той форме,
в какой они лежат в базе (снято чтением 20–21.10.2026): атрибуты SP-API
(`listing_attributes.raw->attributes`), тайтл и поля снапшота ScrapingDog.
Форма повторяет настоящую намеренно — см. AGENTS.md, правило 4: фикстура
другой формы запирает не тот случай.
"""
MP = "A1RKKUPIHCS9HS"


def v(value, **kw):
    return [dict(value=value, marketplace_id=MP, **kw)]


def u(value, unit):
    return [{"unit": unit, "value": value, "marketplace_id": MP}]


def texts(*items):
    return [{"value": i, "language_tag": "es_ES", "marketplace_id": MP} for i in items]


PILOT = {
    "B0H75P364R": dict(  # DGA-201M — аккумуляторная болгарка, набор
        title="Amoladora Angular Dnipro-M DGA-201M 20V, con Batería de 6Ah y Cargador",
        amazon_type="DISC_GRINDER_TOOL",
        attributes={
            "maximum_rotational_speed": u(10000.0, "rpm"),
            "wheel": [{"diameter": [{"unit": "millimeters", "decimal_value": 125.0}], "marketplace_id": MP}],
            "model_name": texts("DGA-201M"),
            "included_components": texts("Amoladora DGA-201M", "Bateria BP-260 de 6Ah", "Cargador FC-230",
                                         "Manual de usuario"),
            "power_source_type": texts("Funciona con batería"),
            "set_name": texts("Set│Bateria 6Ah + Cargador"),
        },
        product_information={"Marca": "Dnipro-M", "Nmero Modelo": "S5_78739000",
                             "Elementos incluidos": "Amoladora DGA-201M, Bateria BP-260 de 6Ah, Cargador FC-230, Manual de usuario",
                             "Velocidad mxima de rotacin": "10000 RPM"},
        item_highlight="Velocidad máxima de 10.000 rpm │ Apta para metal, piedra, granito y mármol │ Incluye batería BP-260 6Ah y cargador",
    ),
    "B0FZFCQN3H": dict(  # GL-240 — сетевая болгарка 2400 Вт
        title="Amoladora Angular Dnipro-M GL-240 2400W 230 mm, 6500 RPM, Giratoria M14",
        amazon_type="DISC_GRINDER_TOOL",
        attributes={
            "horsepower": u(2400.0, "watts"), "wattage": u(2400.0, "watts"),
            "maximum_rotational_speed": u(6500.0, "rpm"),
            "wheel": [{"diameter": [{"unit": "millimeters", "decimal_value": 230.0}], "marketplace_id": MP}],
            "power_source_type": texts("Cable eléctrico"),
            "set_name": texts("2400W-230mm"),
        },
        product_information={"Marca": "Dnipro-M"},
        item_highlight="",
    ),
    "B0H75XRDBK": dict(  # DHR-202BC — перфоратор, набор; аккумулятор в атрибуте 4 Ah, в наборе 6Ah
        title="Martillo Perforador Dnipro-M DHR-202BC Ultra 20V, con Batería de 6Ah",
        amazon_type="DRILL",
        attributes={
            "battery": [{"weight": [{"unit": "grams", "value": 700.0}],
                         "capacity": [{"unit": "amp_hours", "value": 4.0}], "marketplace_id": MP,
                         "cell_composition": [{"value": "lithium_ion"}]}],
            "drill_type": v("hammer_drill"),
            "drilling_capacity_metal": u(13.0, "millimeters"),
            "included_components": texts("Batería recargable BP-260 6A/h", "Cargador FC-230"),
            "maximum_rotational_speed": u(1550.0, "rpm"),
            "maximum_torque": u(50.0, "newton_meters"),
            "model_name": texts("DHR-202BC ULTRA"),
            "power_source_type": texts("Baterías"),
            "set_name": texts("Set | 6Ah + Cargador"),
            "voltage": u(20.0, "volts"),
        },
        product_information={"Marca": "Dnipro-M"},
        item_highlight="",
    ),
    "B0GTRRBZNK": dict(  # DSC-201BC — циркулярная пила; Ø диска только в тексте
        title="Sierra Circular a Batería Dnipro-M DSC-201BC 20V, Disco 165mm, con LED",
        amazon_type="SAW",
        attributes={
            "included_components": texts("Manual de usuario"),
            "model_name": texts("DSC-201BC"),
            "power_source_type": texts("Funciona con batería"),
        },
        product_information={"Marca": "Dnipro-M", "Elementos incluidos": "Manual de usuario",
                             "Destacado del artculo": "Disco de 165 mm, corte de 55 mm a 90° │ Base de aluminio fundido, LED │ 47% más autonomía que el modelo anterior",
                             "Fuente de alimentacin": "Funciona con batería"},
        item_highlight="Disco de 165 mm, corte de 55 mm a 90° │ Base de aluminio fundido, LED │ 47% más autonomía que el modelo anterior",
    ),
    "B0DK5VZYVD": dict(  # CD-200BC — шуруповёрт
        title="Taladro Atornillador Dnipro-M CD-200BC Ultra 20V 60Nm, con Batería 4Ah",
        amazon_type="DRILL",
        attributes={
            "included_components": texts("Batería recargable"),
            "item_torque": u(60.0, "newton_meters"), "maximum_torque": u(60.0, "newton_meters"),
            "maximum_power": u(432.0, "watts"), "wattage": u(432.0, "watts"),
            "maximum_rotational_speed": u(1700.0, "rpm"), "speed": u(1700.0, "rpm"),
            "model_name": texts("CD-200BC Ultra"),
            "power_source_type": texts("Baterías"),
            "voltage": u(20.0, "volts"),
        },
        product_information={"Marca": "Dnipro-M"},
        item_highlight="",
    ),
}
