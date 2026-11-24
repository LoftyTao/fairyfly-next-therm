# coding=utf-8
import pytest
import uuid

from fairyfly.typing import therm_id_from_uuid

from fairyfly_next_therm.material.cavity import CavityMaterial
from fairyfly_next_therm.material.gas import Gas, PureGas
from fairyfly_next_therm.material.solid import SolidMaterial
from fairyfly_next_therm.material.hygrothermal import HygrothermalMaterial
from fairyfly_next_therm.material.xmlutil import extract_all_materials_from_xml_file
from fairyfly_next_therm.lib.gases import air, _gases


def test_cavity_material_init():
    """Test the initialization of CavityMaterialMaterial objects and basic properties."""
    mat_id = uuid.uuid4()
    air_gap = CavityMaterial(air, 'ISO15099', 0.95, None, identifier=mat_id)
    air_gap.display_name = 'ISO Air Gap'
    str(air_gap)  # test the string representation of the material
    air_gap_dup = air_gap.duplicate()

    assert air_gap.identifier == air_gap_dup.identifier == str(mat_id)
    assert air_gap.display_name == air_gap_dup.display_name == 'ISO Air Gap'
    assert air_gap.gas == air_gap_dup.gas == air
    assert air_gap.emissivity == air_gap_dup.emissivity == 0.95
    assert air_gap.emissivity_back == air_gap_dup.emissivity_back == 0.95

    with pytest.raises(AssertionError):
        air_gap.gas = 'Air'


def test_cavity_material_equivalency():
    """Test the equality of a material to another CavityMaterial."""
    air_gap_1 = CavityMaterial(air, 'ISO15099', 0.95, None)
    air_gap_1.display_name = 'ISO Air Gap'
    air_gap_2 = air_gap_1.duplicate()
    gas_id = uuid.uuid4()
    co2_pure = PureGas(0.0146, 0.000014, 827.73)
    co2_pure.specific_heat_ratio = 1.4
    co2_pure.molecular_weight = 44
    co2 = Gas([co2_pure], [1], identifier=gas_id)
    co2.display_name = 'CO2'
    co2_gap = CavityMaterial(co2, 'ISO15099', 0.95, None)
    co2_gap.display_name = 'ISO CO2 Gap'

    assert air_gap_1 == air_gap_2
    assert air_gap_1 != co2_gap
    collection = [air_gap_1, air_gap_2, co2_gap]
    assert len(set(collection)) == 2

    air_gap_2.cavity_model = 'CEN'
    assert air_gap_1 != air_gap_2
    assert len(set(collection)) == 3


def test_cavity_material_lockability():
    """Test the lockability of the CavityMaterial."""
    air_gap = CavityMaterial(air, 'ISO15099', 0.95, None)
    air_gap.cavity_model = 'CEN'
    air_gap.lock()
    with pytest.raises(AttributeError):
        air_gap.cavity_model = 'NFRC'
    air_gap.unlock()
    air_gap.cavity_model = 'NFRC'


def test_cavity_material_to_from_xml():
    """Test the initialization of CavityMaterial objects from XML elements."""
    gas_id = uuid.uuid4()
    co2_pure = PureGas(0.0146, 0.000014, 827.73)
    co2_pure.specific_heat_ratio = 1.4
    co2_pure.molecular_weight = 44
    co2 = Gas([co2_pure], [1], identifier=gas_id)
    co2.display_name = 'CO2'
    mat_id = uuid.uuid4()
    co2_gap = CavityMaterial(co2, 'ISO15099', 0.95, None, identifier=mat_id)
    co2_gap.display_name = 'ISO CO2 Gap'
    xml_mat = co2_gap.to_therm_xml_str()
    co2_gap_dup = CavityMaterial.from_therm_xml_str(xml_mat, {'CO2': co2})

    assert co2_gap == co2_gap_dup
    assert co2_gap.therm_uuid == co2_gap_dup.therm_uuid == therm_id_from_uuid(str(mat_id))
    assert co2_gap.display_name == co2_gap_dup.display_name == 'ISO CO2 Gap'
    assert co2_gap.cavity_model == co2_gap_dup.cavity_model == 'ISO15099'
    assert co2_gap.gas == co2_gap_dup.gas == co2
    assert co2_gap.emissivity == co2_gap_dup.emissivity == 0.95
    assert co2_gap.emissivity_back == co2_gap_dup.emissivity_back == 0.95


def test_cavity_material_dict_methods():
    """Test the to/from dict methods."""
    gas_id = uuid.uuid4()
    co2_pure = PureGas(0.0146, 0.000014, 827.73)
    co2_pure.specific_heat_ratio = 1.4
    co2_pure.molecular_weight = 44
    co2 = Gas([co2_pure], [1], identifier=gas_id)
    co2.display_name = 'CO2'
    mat_id = uuid.uuid4()
    co2_gap = CavityMaterial(co2, 'ISO15099', 0.95, None, identifier=mat_id)
    co2_gap.display_name = 'ISO CO2 Gap'

    material_dict = co2_gap.to_dict()
    co2_gap_dup = CavityMaterial.from_dict(material_dict)

    mat_dict_abridged = co2_gap.to_dict(abridged=True)
    co2_gap_dup2 = CavityMaterial.from_dict_abridged(mat_dict_abridged, {str(gas_id): co2})

    assert material_dict == co2_gap_dup.to_dict()
    assert mat_dict_abridged == co2_gap_dup2.to_dict(abridged=True)
    assert co2_gap == co2_gap_dup == co2_gap_dup2
    assert co2_gap.identifier == co2_gap_dup.identifier == co2_gap_dup2.identifier == str(mat_id)
    assert co2_gap.display_name == co2_gap_dup.display_name == co2_gap_dup2.display_name == 'ISO CO2 Gap'
    assert co2_gap.cavity_model == co2_gap_dup.cavity_model == co2_gap_dup2.cavity_model == 'ISO15099'
    assert co2_gap.emissivity == co2_gap_dup.emissivity == co2_gap_dup2.emissivity == 0.95
    assert co2_gap.emissivity_back == co2_gap_dup.emissivity_back == co2_gap_dup2.emissivity_back == 0.95


def test_extract_all_materials_from_xml_file():
    """Test the extract_all_materials_from_xml_file method."""
    lbnl_mat_file = './tests/assets/xml/Materials.xml'
    solids, cavities = extract_all_materials_from_xml_file(lbnl_mat_file, _gases)

    assert len(solids) == 97
    for solid in solids:
        assert isinstance(solid, (SolidMaterial, HygrothermalMaterial))
    assert len(cavities) == 4
    for cavity in cavities:
        assert isinstance(cavity, CavityMaterial)


def test_lbnl_library_hygrothermal_classification():
    """Pin the LBNL library split between dry and hygrothermal solids.

    Records carrying moisture storage or transport tables load as
    HygrothermalMaterial; records limited to the dry scalar set keep
    loading as SolidMaterial (the pre-extension behavior).
    """
    lbnl_mat_file = './tests/assets/xml/Materials.xml'
    solids, _ = extract_all_materials_from_xml_file(lbnl_mat_file, _gases)
    hygro_names = sorted(
        solid.display_name for solid in solids
        if isinstance(solid, HygrothermalMaterial))
    dry_names = [solid.display_name for solid in solids
                 if isinstance(solid, SolidMaterial)]

    assert hygro_names == [
        '3-ply cross-laminated panel', 'Aerated Concrete',
        'Cellulosic Fiber', 'Chipboard', 'Cottaer Sandstone',
        'Fiberglass Batts', 'Gypsum Board Exterior',
        'Gypsum Board Interior', 'Hardwoods (Deciduous)',
        'Laminated panel', 'OSB Board', 'Plywood',
        'Softwoods (Coniferous)', 'Stucco']
    assert len(dry_names) == 97 - len(hygro_names)


def test_invalid_hygrothermal_record_is_rejected(tmp_path):
    """A record with extended hygrothermal tags that fail validation is an
    explicit error, not a silently skipped material."""
    bad_material = '''<?xml version="1.0"?>
<Materials><Version>1</Version>
  <Material>
    <UUID>11111111-2222-3333-4444-555555555555</UUID>
    <Name>Bad Moisture Material</Name>
    <Solid><HygroThermal>
      <ThermalConductivityDry>0.5</ThermalConductivityDry>
      <MoistureStorageFunction>
        <TableValue><x>0.5</x><y>10</y></TableValue>
        <TableValue><x>0.5</x><y>20</y></TableValue>
      </MoistureStorageFunction>
    </HygroThermal></Solid>
  </Material>
</Materials>'''
    xml_path = tmp_path / 'bad_materials.xml'
    xml_path.write_text(bad_material)

    with pytest.raises(ValueError, match='Bad Moisture Material'):
        extract_all_materials_from_xml_file(str(xml_path), _gases)


def test_nested_hygrothermal_fields_are_rejected(tmp_path):
    """Unknown nested HygroThermal content is an explicit error, not dropped.

    The extractor checks only direct children; fields nested inside a table
    element or inside a TableValue pair used to be silently ignored.
    """
    for inner in (
            # a nested foreign field inside a known table element
            '<MoistureStorageFunction>'
            '<TableValue><x>0.5</x><y>10</y></TableValue>'
            '<DryingCurve/>'
            '</MoistureStorageFunction>',
            # a nested foreign field inside a TableValue pair
            '<MoistureStorageFunction>'
            '<TableValue><x>0.5</x><y>10</y><z>1</z></TableValue>'
            '</MoistureStorageFunction>',
            # a nested foreign field inside an x leaf of a TableValue pair
            '<MoistureStorageFunction>'
            '<TableValue><x>0.5<extra/></x><y>10</y></TableValue>'
            '</MoistureStorageFunction>',
            # a foreign direct child alongside the dry scalar set
            '<ThermalConductivityDry>0.5</ThermalConductivityDry>'
            '<HygroThermalExtension/>'):
        bad_material = '''<?xml version="1.0"?>
<Materials><Version>1</Version>
  <Material>
    <UUID>11111111-2222-3333-4444-555555555555</UUID>
    <Name>Nested Field Material</Name>
    <Solid><HygroThermal>
      <ThermalConductivityDry>0.5</ThermalConductivityDry>
      {}
    </HygroThermal></Solid>
  </Material>
</Materials>'''.format(inner)
        xml_path = tmp_path / 'nested_materials.xml'
        xml_path.write_text(bad_material)

        with pytest.raises(ValueError, match='Nested Field Material'):
            extract_all_materials_from_xml_file(str(xml_path), _gases)


def test_invalid_dry_record_keeps_legacy_skip(tmp_path):
    """Dry solid records keep the legacy tolerant load behavior."""
    bad_material = '''<?xml version="1.0"?>
<Materials><Version>1</Version>
  <Material>
    <Name>No Conductivity</Name>
    <Solid><HygroThermal><BulkDensity>500</BulkDensity></HygroThermal></Solid>
  </Material>
  <Material>
    <UUID>11111111-2222-3333-4444-555555555555</UUID>
    <Name>Good Solid</Name>
    <Solid><HygroThermal>
      <ThermalConductivityDry>0.5</ThermalConductivityDry>
    </HygroThermal></Solid>
  </Material>
</Materials>'''
    xml_path = tmp_path / 'mixed_materials.xml'
    xml_path.write_text(bad_material)

    solids, cavities = extract_all_materials_from_xml_file(
        str(xml_path), _gases)
    assert [solid.display_name for solid in solids] == ['Good Solid']
