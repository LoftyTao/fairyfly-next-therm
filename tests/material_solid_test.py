# coding=utf-8
import pytest
import uuid

from fairyfly_next_therm.material.solid import SolidMaterial


def test_solid_material_init():
    """Test the initialization of SolidMaterial objects and basic properties."""
    mat_id = uuid.uuid4()
    concrete = SolidMaterial(0.5, 0.95, None, 800, 0.81, 1200, 7.9, identifier=mat_id)
    concrete.display_name = 'Concrete'
    str(concrete)  # test the string representation of the material
    concrete_dup = concrete.duplicate()

    assert concrete.identifier == concrete_dup.identifier == str(mat_id)
    assert concrete.display_name == concrete_dup.display_name == 'Concrete'
    assert concrete.conductivity == concrete_dup.conductivity == 0.5
    assert concrete.emissivity == concrete_dup.emissivity == 0.95
    assert concrete.emissivity_back == concrete_dup.emissivity_back == 0.95
    assert concrete.density == concrete_dup.density == 800
    assert concrete.porosity == concrete_dup.porosity == 0.81
    assert concrete.specific_heat == concrete_dup.specific_heat == 1200
    assert concrete.vapor_diffusion_resistance == concrete_dup.vapor_diffusion_resistance == 7.9
    assert concrete.resistivity == 1 / 0.5

    with pytest.raises(AssertionError):
        concrete.conductivity = 0


def test_solid_material_equivalency():
    """Test the equality of a material to another SolidMaterial."""
    concrete_1 = SolidMaterial(0.5, 0.95, None, 800, 0.81, 1200, 7.9)
    concrete_1.display_name = 'Concrete'
    concrete_2 = concrete_1.duplicate()
    insulation = SolidMaterial(0.049, 0.9, None, 265, None, 836)
    insulation.display_name = 'Insulation'

    assert concrete_1 == concrete_2
    assert concrete_1 != insulation
    collection = [concrete_1, concrete_2, insulation]
    assert len(set(collection)) == 2

    concrete_2.density = 600
    assert concrete_1 != concrete_2
    assert len(set(collection)) == 3


def test_solid_material_lockability():
    """Test the lockability of the SolidMaterial."""
    concrete = SolidMaterial(0.5, 0.95, None, 800, 0.81, 1200, 7.9)
    concrete.density = 600
    concrete.lock()
    with pytest.raises(AttributeError):
        concrete.density = 700
    concrete.unlock()
    concrete.density = 700


def test_solid_material_invalid():
    """Test the initialization of SolidMaterial objects with invalid properties."""
    concrete = SolidMaterial(0.5, 0.95, None, 800, 0.81, 1200, 7.9)

    with pytest.raises(ValueError):
        concrete.identifier = 'test_identifier'
    with pytest.raises(AssertionError):
        concrete.conductivity = -1
    with pytest.raises(AssertionError):
        concrete.emissivity = 2
    with pytest.raises(AssertionError):
        concrete.emissivity_back = 2
    with pytest.raises(AssertionError):
        concrete.density = -1
    with pytest.raises(AssertionError):
        concrete.specific_heat = -1


def test_solid_material_to_from_xml():
    """Test the initialization of SolidMaterial objects from XML elements."""
    mat_id = uuid.uuid4()
    concrete = SolidMaterial(0.5, 0.95, None, 800, 0.81, 1200, 7.9, identifier=mat_id)
    concrete.display_name = 'Concrete'
    xml_mat = concrete.to_therm_xml_str()
    concrete_dup = SolidMaterial.from_therm_xml_str(xml_mat)

    assert concrete == concrete_dup
    assert concrete.identifier == concrete_dup.identifier == str(mat_id)
    assert concrete.display_name == concrete_dup.display_name == 'Concrete'
    assert concrete.conductivity == concrete_dup.conductivity == 0.5
    assert concrete.emissivity == concrete_dup.emissivity == 0.95
    assert concrete.emissivity_back == concrete_dup.emissivity_back == 0.95
    assert concrete.density == concrete_dup.density == 800
    assert concrete.porosity == concrete_dup.porosity == 0.81
    assert concrete.specific_heat == concrete_dup.specific_heat == 1200
    assert concrete.vapor_diffusion_resistance == concrete_dup.vapor_diffusion_resistance == 7.9


def test_solid_material_dict_methods():
    """Test the to/from dict methods."""
    mat_id = uuid.uuid4()
    concrete = SolidMaterial(0.5, 0.95, None, 800, 0.81, 1200, 7.9, identifier=mat_id)
    concrete.display_name = 'Concrete'

    material_dict = concrete.to_dict()
    concrete_dup = SolidMaterial.from_dict(material_dict)

    assert material_dict == concrete_dup.to_dict()
    assert concrete == concrete_dup
    assert concrete.identifier == concrete_dup.identifier == str(mat_id)
    assert concrete.display_name == concrete_dup.display_name == 'Concrete'
    assert concrete.conductivity == concrete_dup.conductivity == 0.5
    assert concrete.emissivity == concrete_dup.emissivity == 0.95
    assert concrete.emissivity_back == concrete_dup.emissivity_back == 0.95
    assert concrete.density == concrete_dup.density == 800
    assert concrete.porosity == concrete_dup.porosity == 0.81
    assert concrete.specific_heat == concrete_dup.specific_heat == 1200
    assert concrete.vapor_diffusion_resistance == concrete_dup.vapor_diffusion_resistance == 7.9


def test_model_ffjson_and_thmz_preserve_solid_material(tmp_path):
    """Model and THMZ round trips retain current SolidMaterial properties."""
    import zipfile
    from xml.etree import ElementTree as ET

    from fairyfly.model import Model
    from fairyfly_next_therm.lib.conditions import exterior, interior

    mat_id = uuid.uuid4()
    material = SolidMaterial(0.5, 0.73, 0.41, 800, 0.18, 1200, 42,
                             identifier=mat_id)
    material.display_name = 'Round-trip material'
    material.color = '#123456'
    model = Model.from_layers([100], height=500)
    model.shapes[0].properties.therm.material = material
    model.boundaries[0].properties.therm.condition = exterior
    model.boundaries[1].properties.therm.condition = interior

    ffjson = model.to_ffjson('round-trip', str(tmp_path))
    loaded = Model.from_ffjson(ffjson)
    loaded_material = loaded.shapes[0].properties.therm.material
    assert loaded.to_dict() == model.to_dict()

    thmz = str(tmp_path / 'round-trip.thmz')
    loaded.to_thmz(thmz)
    with zipfile.ZipFile(thmz) as archive:
        materials_xml = ET.fromstring(archive.read('Materials.xml'))
        model_xml = ET.fromstring(archive.read('Model.xml'))
    exported = SolidMaterial.from_therm_xml(materials_xml.find('Material'))
    for actual in (loaded_material, exported):
        assert actual.identifier == str(mat_id)
        assert actual.color.to_hex() == '#123456'
        assert (actual.conductivity, actual.emissivity, actual.emissivity_back,
                actual.density, actual.porosity, actual.specific_heat,
                actual.vapor_diffusion_resistance) == \
            (0.5, 0.73, 0.41, 800, 0.18, 1200, 42)
    assert model_xml.find('.//MaterialUUID').text == str(mat_id)
