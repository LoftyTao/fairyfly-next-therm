# coding=utf-8
import pytest
import uuid
import xml.etree.ElementTree as ET

from fairyfly_next_therm.material.hygrothermal import HygrothermalMaterial


def _brick():
    mat_id = uuid.uuid4()
    brick = HygrothermalMaterial(
        0.62, density=1700, porosity=0.28, specific_heat=840,
        vapor_diffusion_resistance=38, roughness='Medium Rough',
        moisture_storage_function=[[0.0, 0.0], [0.5, 60.0], [0.95, 120.0],
                                   [1.0, 300.0]],
        liquid_transport_suction=[[0.0, 0.0], [120.0, 1e-6]],
        liquid_transport_redistribution=[[0.0, 0.0], [300.0, 1e-10]],
        conductivity_moisture_dependent=[[0.0, 0.62], [300.0, 0.8]],
        conductivity_temperature_dependent=[[10.0, 0.62], [40.0, 0.64]],
        diffusion_moisture_dependent=[[0.0, 38.0], [300.0, 10.0]],
        enthalpy_temperature_dependent=[[10.0, 840], [40.0, 900]],
        reference_water_content=60, free_water_saturation=300,
        water_absorption_coefficient=0.5, drying_factor=2,
        conductivity_moisture_supplement=0.0006,
        conductivity_temperature_supplement=0.0005,
        conductivity_design_value=0.65, typical_built_in_moisture=45,
        default_thickness=0.2, material_information='test brick',
        emissivity=0.93, emissivity_back=0.85, identifier=mat_id)
    brick.display_name = 'Brick'
    return brick


def test_hygrothermal_init():
    """Test the initialization of HygrothermalMaterial objects."""
    brick = _brick()
    str(brick)  # test the string representation of the material
    brick_dup = brick.duplicate()

    assert brick.identifier == brick_dup.identifier
    assert brick.display_name == brick_dup.display_name == 'Brick'
    assert brick.conductivity == brick_dup.conductivity == 0.62
    assert brick.density == brick_dup.density == 1700
    assert brick.roughness == brick_dup.roughness == 'Medium Rough'
    assert brick.moisture_storage_function == brick_dup.moisture_storage_function
    assert brick.liquid_transport_suction == brick_dup.liquid_transport_suction
    assert brick.enthalpy_temperature_dependent == \
        brick_dup.enthalpy_temperature_dependent
    assert brick.free_water_saturation == brick_dup.free_water_saturation == 300
    assert brick.emissivity == brick_dup.emissivity == 0.93
    assert brick.emissivity_back == brick_dup.emissivity_back == 0.85
    assert brick.resistivity == brick_dup.resistivity == 1 / 0.62


def test_hygrothermal_equivalency():
    """Test the equality of a HygrothermalMaterial to another."""
    brick_1 = _brick()
    brick_2 = brick_1.duplicate()
    stone = HygrothermalMaterial(2.2, density=2200, specific_heat=900)
    stone.display_name = 'Sandstone'

    assert brick_1 == brick_2
    assert brick_1 != stone
    collection = [brick_1, brick_2, stone]
    assert len(set(collection)) == 2

    brick_2.density = 1000
    assert brick_1 != brick_2
    assert len(set(collection)) == 3


def test_hygrothermal_lockability():
    """Test the lockability of the HygrothermalMaterial."""
    brick = _brick()
    brick.density = 1900
    brick.lock()
    with pytest.raises(AttributeError):
        brick.density = 0
    brick.unlock()
    brick.density = 1700


def test_hygrothermal_table_checks():
    """Moisture tables need at least one point with increasing x."""
    mat = HygrothermalMaterial(0.5, moisture_storage_function=[[0.5, 10.0]])
    assert mat.moisture_storage_function == ((0.5, 10.0),)
    with pytest.raises(ValueError):
        HygrothermalMaterial(0.5, moisture_storage_function=[])
    with pytest.raises(ValueError):
        HygrothermalMaterial(
            0.5, moisture_storage_function=[[0.5, 10.0], [0.5, 20.0]])
    with pytest.raises(ValueError):
        HygrothermalMaterial(
            0.5, liquid_transport_suction=[[0.0, 0.0], [0.0]])
    with pytest.raises(ValueError):
        HygrothermalMaterial(0.5, roughness='Shiny')
    with pytest.raises(AssertionError):
        HygrothermalMaterial(0.5, porosity=1.5)


def test_hygrothermal_to_from_xml():
    """Test the roundtrip of HygrothermalMaterial through THERM XML."""
    brick = _brick()
    xml_str = brick.to_therm_xml_str()
    brick_dup = HygrothermalMaterial.from_therm_xml_str(xml_str)

    assert brick == brick_dup
    assert brick_dup.moisture_storage_function == brick.moisture_storage_function
    assert brick_dup.roughness == brick.roughness == 'Medium Rough'
    root = ET.fromstring(xml_str)
    hyt = root.find('Solid/HygroThermal')
    assert hyt.findtext('ThermalConductivityDry') == '0.62'
    table = hyt.find('MoistureStorageFunction')
    assert len(table.findall('TableValue')) == 4
    assert table.findall('TableValue')[0].findtext('x') == '0.0'
    assert hyt.findtext('TypicalBuiltInMoisture') == '45.0'
    assert hyt.findtext('MaterialInformation') == 'test brick'
    # the upstream serializer order keeps ThermalConductivityDry after
    # SpecificHeatCapacityDry and before WaterVaporDiffusionResistanceFactor
    tags = [child.tag for child in hyt]
    assert tags.index('ThermalConductivityDry') == \
        tags.index('SpecificHeatCapacityDry') + 1


def test_hygrothermal_from_xml_rejects_nested_fields():
    """from_therm_xml itself rejects unsupported nested content."""
    brick = _brick()
    root = ET.fromstring(brick.to_therm_xml_str())
    hyt = root.find('Solid/HygroThermal')
    table = hyt.find('MoistureStorageFunction')
    ET.SubElement(table, 'UnknownNestedField')

    with pytest.raises(ValueError, match='unsupported'):
        HygrothermalMaterial.from_therm_xml(root)
    # foreign fields inside TableValue pairs are also rejected
    root_2 = ET.fromstring(brick.to_therm_xml_str())
    tv = root_2.find('Solid/HygroThermal/MoistureStorageFunction/TableValue')
    ET.SubElement(tv, 'z')
    with pytest.raises(ValueError, match='unsupported'):
        HygrothermalMaterial.from_therm_xml(root_2)


def test_hygrothermal_from_xml_rejects_fields_nested_inside_leaves():
    """Unmodeled content inside x/y pair leaves and scalar leaves is rejected.

    The extractor and the direct-children scan cannot see elements nested
    inside an x or y leaf (``<x>0.5<extra/></x>``), inside a modeled scalar
    leaf (``<BulkDensity><value>1700</value></BulkDensity>``), or attributes
    carried by modeled elements; all of it must be an explicit error rather
    than data silently dropped by the parse.
    """
    brick = _brick()
    # a foreign field nested inside an x leaf
    root = ET.fromstring(brick.to_therm_xml_str())
    leaf = root.find(
        'Solid/HygroThermal/MoistureStorageFunction/TableValue/x')
    ET.SubElement(leaf, 'extra')
    with pytest.raises(ValueError, match='unsupported'):
        HygrothermalMaterial.from_therm_xml(root)
    # a foreign field nested inside a y leaf
    root = ET.fromstring(brick.to_therm_xml_str())
    leaf = root.find(
        'Solid/HygroThermal/MoistureStorageFunction/TableValue/y')
    ET.SubElement(leaf, 'extra')
    with pytest.raises(ValueError, match='unsupported'):
        HygrothermalMaterial.from_therm_xml(root)
    # a foreign field nested inside a modeled scalar leaf
    root = ET.fromstring(brick.to_therm_xml_str())
    scalar = root.find('Solid/HygroThermal/BulkDensity')
    ET.SubElement(scalar, 'value')
    with pytest.raises(ValueError, match='unsupported'):
        HygrothermalMaterial.from_therm_xml(root)
    # attributes on modeled elements carry unmodeled data too
    root = ET.fromstring(brick.to_therm_xml_str())
    pair = root.find(
        'Solid/HygroThermal/MoistureStorageFunction/TableValue')
    pair.set('source', 'lab')
    with pytest.raises(ValueError, match='unsupported'):
        HygrothermalMaterial.from_therm_xml(root)


def test_hygrothermal_from_xml_rejects_unknown_optical_fields():
    """Fields outside the THERM Optical grammar are rejected explicitly.

    The parse navigates the Optical subtree with targeted .find() calls,
    so a foreign tag or attribute at any depth would be silently dropped
    without a structural whitelist check.
    """
    brick = _brick()
    # a foreign tag directly under Optical
    root = ET.fromstring(brick.to_therm_xml_str())
    ET.SubElement(root.find('Solid/Optical'), 'SpectralData')
    with pytest.raises(ValueError, match='Optical'):
        HygrothermalMaterial.from_therm_xml(root)
    # a foreign tag under Integrated
    root = ET.fromstring(brick.to_therm_xml_str())
    ET.SubElement(root.find('Solid/Optical/Integrated'), 'Ultraviolet')
    with pytest.raises(ValueError, match='Optical'):
        HygrothermalMaterial.from_therm_xml(root)
    # a foreign leaf inside Infrared
    root = ET.fromstring(brick.to_therm_xml_str())
    ET.SubElement(
        root.find('Solid/Optical/Integrated/Infrared'), 'Emissivity-Side')
    with pytest.raises(ValueError, match='Optical'):
        HygrothermalMaterial.from_therm_xml(root)
    # an element nested inside a modeled optical leaf
    root = ET.fromstring(brick.to_therm_xml_str())
    leaf = root.find('Solid/Optical/Integrated/Infrared/Emissivity-Front')
    ET.SubElement(leaf, 'value')
    with pytest.raises(ValueError, match='Optical'):
        HygrothermalMaterial.from_therm_xml(root)
    # an attribute on a modeled optical element
    root = ET.fromstring(brick.to_therm_xml_str())
    root.find('Solid/Optical/Integrated').set('units', 'SI')
    with pytest.raises(ValueError, match='Optical'):
        HygrothermalMaterial.from_therm_xml(root)


def test_hygrothermal_from_xml_rejects_unknown_solid_fields():
    """Foreign children or attributes on Solid itself are rejected."""
    brick = _brick()
    # a foreign sibling of HygroThermal and Optical
    root = ET.fromstring(brick.to_therm_xml_str())
    ET.SubElement(root.find('Solid'), 'Glazing')
    with pytest.raises(ValueError, match='Solid'):
        HygrothermalMaterial.from_therm_xml(root)
    # a duplicated Optical record is schema-invalid and ambiguous
    root = ET.fromstring(brick.to_therm_xml_str())
    dup = ET.SubElement(root.find('Solid'), 'Optical')
    ET.SubElement(dup, 'Integrated')
    with pytest.raises(ValueError, match='Solid'):
        HygrothermalMaterial.from_therm_xml(root)


def _add_optical_range(integrated, range_name, transmittance, reflectance):
    """Append a full Solar or Visible subtree of the THERM serializer shape.

    The canonical serializer writes both Direct and Diffuse components with
    Front and Back sides, each carrying a Transmittance and Reflectance leaf.
    """
    range_el = ET.SubElement(integrated, range_name)
    for comp in ('Direct', 'Diffuse'):
        comp_el = ET.SubElement(range_el, comp)
        for side in ('Front', 'Back'):
            side_el = ET.SubElement(comp_el, side)
            ET.SubElement(side_el, 'Transmittance').text = str(transmittance)
            ET.SubElement(side_el, 'Reflectance').text = str(reflectance)


def test_hygrothermal_from_xml_rejects_unmodeled_optical_values():
    """Schema-legitimate but unmodeled optical values are explicit errors.

    The object models only the Infrared emissivities and the Solar
    Direct/Front transmittance and reflectance. Fields without a modeled
    counterpart (Infrared/Transmittance, every Visible leaf) and Solar
    Diffuse/Back copies that diverge from the modeled Solar Direct/Front
    value would be silently lost on write-back, so they are rejected.
    """
    brick = _brick()
    # an infrared transmittance has no modeled counterpart
    root = ET.fromstring(brick.to_therm_xml_str())
    ET.SubElement(
        root.find('Solid/Optical/Integrated/Infrared'), 'Transmittance').text = '0'
    with pytest.raises(ValueError, match='unmodeled'):
        HygrothermalMaterial.from_therm_xml(root)
    # a Visible range value has no modeled counterpart either
    root = ET.fromstring(brick.to_therm_xml_str())
    integrated = root.find('Solid/Optical/Integrated')
    visible = ET.SubElement(integrated, 'Visible')
    front = ET.SubElement(ET.SubElement(visible, 'Direct'), 'Front')
    ET.SubElement(front, 'Transmittance').text = '0'
    ET.SubElement(front, 'Reflectance').text = '0.3'
    with pytest.raises(ValueError, match='unmodeled'):
        HygrothermalMaterial.from_therm_xml(root)
    # a Solar replica diverging from the modeled Direct/Front value would
    # be dropped by the parser, so it is rejected as well
    root = ET.fromstring(brick.to_therm_xml_str())
    integrated = root.find('Solid/Optical/Integrated')
    _add_optical_range(integrated, 'Solar', '0.2', '0.3')
    divergent = integrated.find('Solar/Diffuse/Back/Reflectance')
    divergent.text = '0.4'
    with pytest.raises(ValueError, match='unmodeled'):
        HygrothermalMaterial.from_therm_xml(root)


def test_hygrothermal_from_xml_accepts_redundant_solar_fields():
    """Solar Diffuse/Back copies matching Direct/Front still parse.

    The serializer replicates the modeled Solar Direct/Front values into
    the three sibling subtrees the schema makes mandatory, so write-back
    loses nothing and these redundant copies are tolerated. Valueless
    elements carry no data to lose and are also tolerated.
    """
    brick = _brick()
    brick.reflectance = 0.3
    brick.transmittance = 0.2
    # our own writer emits the redundant Solar replicas
    mat = HygrothermalMaterial.from_therm_xml_str(brick.to_therm_xml_str())
    assert mat == brick
    assert mat.reflectance == 0.3
    assert mat.transmittance == 0.2
    # a foreign record carrying only the modeled Solar leaves also parses
    root = ET.fromstring(_brick().to_therm_xml_str())
    integrated = root.find('Solid/Optical/Integrated')
    solar = ET.SubElement(integrated, 'Solar')
    front = ET.SubElement(ET.SubElement(solar, 'Direct'), 'Front')
    ET.SubElement(front, 'Transmittance').text = '0.2'
    ET.SubElement(front, 'Reflectance').text = '0.3'
    mat = HygrothermalMaterial.from_therm_xml(root)
    assert mat.transmittance == 0.2
    assert mat.reflectance == 0.3
    # empty subtrees carry no value to lose and are tolerated
    root = ET.fromstring(_brick().to_therm_xml_str())
    integrated = root.find('Solid/Optical/Integrated')
    ET.SubElement(integrated.find('Infrared'), 'Transmittance')
    ET.SubElement(integrated, 'Visible')
    mat = HygrothermalMaterial.from_therm_xml(root)
    assert mat.emissivity == 0.93


def test_hygrothermal_from_xml_rejects_malformed_table_values():
    """A TableValue must hold exactly one x leaf and one y leaf with text."""
    brick = _brick()
    # a TableValue missing its y leaf
    root = ET.fromstring(brick.to_therm_xml_str())
    pair = root.find(
        'Solid/HygroThermal/MoistureStorageFunction/TableValue')
    pair.remove(pair.find('y'))
    with pytest.raises(ValueError, match='TableValue'):
        HygrothermalMaterial.from_therm_xml(root)
    # a TableValue with a duplicate x leaf
    root = ET.fromstring(brick.to_therm_xml_str())
    pair = root.find(
        'Solid/HygroThermal/MoistureStorageFunction/TableValue')
    x_dup = ET.SubElement(pair, 'x')
    x_dup.text = '0.7'
    with pytest.raises(ValueError, match='TableValue'):
        HygrothermalMaterial.from_therm_xml(root)
    # a TableValue whose x leaf carries no text
    root = ET.fromstring(brick.to_therm_xml_str())
    pair = root.find(
        'Solid/HygroThermal/MoistureStorageFunction/TableValue')
    pair.find('x').text = None
    with pytest.raises(ValueError, match='TableValue'):
        HygrothermalMaterial.from_therm_xml(root)


def test_hygrothermal_dict_methods():
    """Test the to/from dict methods."""
    brick = _brick()

    material_dict = brick.to_dict()
    brick_dup = HygrothermalMaterial.from_dict(material_dict)

    assert material_dict == brick_dup.to_dict()
    assert brick == brick_dup
    assert brick_dup.display_name == 'Brick'
    assert brick_dup.moisture_storage_function == brick.moisture_storage_function


def test_hygrothermal_dictutil_dispatch():
    """Test that HygrothermalMaterial dictionaries dispatch correctly."""
    from fairyfly_next_therm.material.dictutil import dict_to_material
    brick = _brick()
    dup = dict_to_material(brick.to_dict())
    assert isinstance(dup, HygrothermalMaterial)
    assert dup == brick


@pytest.mark.parametrize('prop, table', [
    ('moisture_storage_function', [[-0.1, 0]]),
    ('moisture_storage_function', [[1.1, 10]]),
    ('moisture_storage_function', [[0.5, -1]]),
    ('moisture_storage_function', [[0.5, float('inf')]]),
    ('moisture_storage_function', [[float('nan'), 10]]),
    ('moisture_storage_function', [None]),
    ('moisture_storage_function', ['12']),
    ('liquid_transport_suction', [[-1, 0]]),
    ('liquid_transport_suction', [[0, -1e-6]]),
    ('liquid_transport_redistribution', [[0, -1e-6]]),
    ('conductivity_moisture_dependent', [[0, 0]]),
    ('conductivity_temperature_dependent', [[-274, 0.5]]),
    ('conductivity_temperature_dependent', [[10, float('inf')]]),
    ('diffusion_moisture_dependent', [[0, 0]]),
    ('enthalpy_temperature_dependent', [[10, float('nan')]]),
])
def test_hygrothermal_rejects_illegal_table_values(prop, table):
    """Modeled tables reject invalid pairs and physical domains explicitly."""
    with pytest.raises(ValueError, match='THMZ-E2004'):
        HygrothermalMaterial(0.5, **{prop: table})
    with pytest.raises(ValueError, match='THMZ-E2004'):
        HygrothermalMaterial.from_dict(dict(
            type='HygrothermalMaterial', conductivity=0.5, **{prop: table}))


@pytest.mark.parametrize('tag', ['BulkDensity', 'MoistureStorageFunction'])
def test_hygrothermal_rejects_duplicate_hygrothermal_fields(tag):
    """Duplicate single-valued material fields never silently select the first."""
    root = _brick().to_therm_xml()
    hyt = root.find('Solid/HygroThermal')
    hyt.append(ET.fromstring(ET.tostring(hyt.find(tag))))
    with pytest.raises(ValueError, match='THMZ-E2002'):
        HygrothermalMaterial.from_therm_xml(root)


def test_hygrothermal_missing_conductivity_is_explicit():
    """A missing dry conductivity is a field error, not an AttributeError."""
    root = _brick().to_therm_xml()
    hyt = root.find('Solid/HygroThermal')
    hyt.remove(hyt.find('ThermalConductivityDry'))
    with pytest.raises(ValueError, match='THMZ-E2003'):
        HygrothermalMaterial.from_therm_xml(root)
