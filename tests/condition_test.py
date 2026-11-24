# coding=utf-8
import pytest
import uuid

from fairyfly_next_therm.condition.steadystate import SteadyState


def test_condition_init():
    """Test the initialization of SteadyState objects and basic properties."""
    cond_id = uuid.uuid4()
    nfrc_ext = SteadyState(-18, 26, identifier=cond_id)
    nfrc_ext.display_name = 'NFRC 100-2010 Exterior'
    str(nfrc_ext)  # test the string representation of the condition
    nfrc_ext_dup = nfrc_ext.duplicate()

    assert nfrc_ext.identifier == nfrc_ext_dup.identifier == str(cond_id)
    assert nfrc_ext.display_name == nfrc_ext_dup.display_name == 'NFRC 100-2010 Exterior'
    assert nfrc_ext.temperature == nfrc_ext_dup.temperature == -18
    assert nfrc_ext.film_coefficient == nfrc_ext_dup.film_coefficient == 26
    assert nfrc_ext.emissivity == nfrc_ext_dup.emissivity == 1
    assert nfrc_ext.radiant_temperature == nfrc_ext_dup.radiant_temperature == -18
    assert nfrc_ext.heat_flux == nfrc_ext_dup.heat_flux == 0
    assert nfrc_ext.relative_humidity == nfrc_ext_dup.relative_humidity == 0.5


def test_condition_equivalency():
    """Test the equality of a condition to another SteadyState."""
    nfrc_ext_1 = SteadyState(-18, 26)
    nfrc_ext_1.display_name = 'NFRC 100-2010 Exterior'
    nfrc_ext_2 = nfrc_ext_1.duplicate()
    interior = SteadyState(21, 2.44)
    interior.display_name = 'Interior Wood/Vinyl Frame'

    assert nfrc_ext_1 == nfrc_ext_2
    assert nfrc_ext_1 != interior
    collection = [nfrc_ext_1, nfrc_ext_2, interior]
    assert len(set(collection)) == 2

    nfrc_ext_2.temperature = 36
    assert nfrc_ext_1 != nfrc_ext_2
    assert len(set(collection)) == 3


def test_condition_lockability():
    """Test the lockability of the SteadyState."""
    nfrc_ext = SteadyState(-18, 26)
    nfrc_ext.temperature = 36
    nfrc_ext.lock()
    with pytest.raises(AttributeError):
        nfrc_ext.temperature = 0
    nfrc_ext.unlock()
    nfrc_ext.temperature = -12


def test_condition_to_from_xml():
    """Test the initialization of SteadyState objects from XML elements."""
    cond_id = uuid.uuid4()
    nfrc_ext = SteadyState(-18, 26, identifier=cond_id)
    nfrc_ext.display_name = 'NFRC 100-2010 Exterior'
    xml = nfrc_ext.to_therm_xml()
    assert xml.findtext(
        'Comprehensive/Radiation/BlackBodyRadiation/Temperature') == '-18.0'
    assert xml.findtext(
        'Comprehensive/Radiation/BlackBodyRadiation/Emissivity') == '1.0'
    assert xml.findtext(
        'Comprehensive/Radiation/BlackBodyRadiation/ViewFactor') == '1'
    assert xml.findtext('Comprehensive/ConstantFlux/Flux') == '0.0'
    xml_cond = nfrc_ext.to_therm_xml_str()
    nfrc_ext_dup = SteadyState.from_therm_xml_str(xml_cond)

    assert nfrc_ext == nfrc_ext_dup
    assert nfrc_ext.identifier == nfrc_ext_dup.identifier == str(cond_id)
    assert nfrc_ext.display_name == nfrc_ext_dup.display_name == 'NFRC 100-2010 Exterior'
    assert nfrc_ext.temperature == nfrc_ext_dup.temperature == -18
    assert nfrc_ext.film_coefficient == nfrc_ext_dup.film_coefficient == 26
    assert nfrc_ext.emissivity == nfrc_ext_dup.emissivity == 1
    assert nfrc_ext.radiant_temperature == nfrc_ext_dup.radiant_temperature == -18
    assert nfrc_ext.heat_flux == nfrc_ext_dup.heat_flux == 0
    assert nfrc_ext.relative_humidity == nfrc_ext_dup.relative_humidity == 0.5


def test_condition_from_black_body_radiation_xml():
    xml = '''<BoundaryCondition>
        <UUID>1810f37a-de4d-4e2d-95d5-09fe01157c34</UUID>
        <Name>Radiant boundary</Name>
        <Comprehensive>
            <RelativeHumidity>0.5</RelativeHumidity>
            <Convection>
                <Temperature>21</Temperature>
                <FilmCoefficient>3</FilmCoefficient>
            </Convection>
            <ConstantFlux><Flux>125</Flux></ConstantFlux>
            <Radiation>
                <BlackBodyRadiation>
                    <Temperature>-8</Temperature>
                    <Emissivity>0.72</Emissivity>
                    <ViewFactor>1</ViewFactor>
                </BlackBodyRadiation>
            </Radiation>
        </Comprehensive>
    </BoundaryCondition>'''
    condition = SteadyState.from_therm_xml_str(xml)

    assert condition.temperature == 21
    assert condition.film_coefficient == 3
    assert condition.radiant_temperature == -8
    assert condition.emissivity == 0.72
    assert condition.heat_flux == 125


def test_condition_to_therm_xml_keeps_default_adiabatic_simple():
    condition = SteadyState(0, 0)

    xml = condition.to_therm_xml()

    assert xml.find('Simplified/FilmCoefficient').text == '0'
    assert xml.find('Comprehensive') is None


def test_condition_from_therm_xml_preserves_radiation_with_zero_film():
    xml = '''<BoundaryCondition>
        <UUID>1810f37a-de4d-4e2d-95d5-09fe01157c34</UUID>
        <Comprehensive>
            <RelativeHumidity>0.5</RelativeHumidity>
            <Convection>
                <Temperature>21</Temperature>
                <FilmCoefficient>0</FilmCoefficient>
            </Convection>
            <ConstantFlux><Flux>0</Flux></ConstantFlux>
            <Radiation>
                <AutomaticEnclosure>
                    <Temperature>21</Temperature>
                    <Emissivity>1</Emissivity>
                </AutomaticEnclosure>
            </Radiation>
        </Comprehensive>
    </BoundaryCondition>'''
    condition = SteadyState.from_therm_xml_str(xml)

    output = condition.to_therm_xml()

    assert output.find('Simplified') is None
    assert output.findtext(
        'Comprehensive/Radiation/BlackBodyRadiation/Temperature') == '21.0'
    assert output.findtext(
        'Comprehensive/Radiation/BlackBodyRadiation/Emissivity') == '1.0'
    assert output.findtext('Comprehensive/ConstantFlux/Flux') == '0.0'


def test_condition_to_therm_xml_keeps_radiation_and_flux_when_film_is_zero():
    condition = SteadyState(21, 0, emissivity=0.72, radiant_temperature=-8,
                            heat_flux=125)

    xml = condition.to_therm_xml()

    assert xml.find('Simplified') is None
    assert xml.findtext('Comprehensive/Convection/FilmCoefficient') == '0.0'
    assert xml.findtext('Comprehensive/ConstantFlux/Flux') == '125.0'
    assert xml.findtext(
        'Comprehensive/Radiation/BlackBodyRadiation/Temperature') == '-8.0'
    assert xml.findtext(
        'Comprehensive/Radiation/BlackBodyRadiation/Emissivity') == '0.72'
    assert xml.findtext(
        'Comprehensive/Radiation/BlackBodyRadiation/ViewFactor') == '1'


def test_condition_dict_methods():
    """Test the to/from dict methods."""
    cond_id = uuid.uuid4()
    nfrc_ext = SteadyState(-18, 26, identifier=cond_id)
    nfrc_ext.display_name = 'NFRC 100-2010 Exterior'

    condition_dict = nfrc_ext.to_dict()
    nfrc_ext_dup = SteadyState.from_dict(condition_dict)

    assert condition_dict == nfrc_ext_dup.to_dict()
    assert nfrc_ext == nfrc_ext_dup
    assert nfrc_ext.identifier == nfrc_ext_dup.identifier == str(cond_id)
    assert nfrc_ext.display_name == nfrc_ext_dup.display_name == 'NFRC 100-2010 Exterior'
    assert nfrc_ext.temperature == nfrc_ext_dup.temperature == -18
    assert nfrc_ext.film_coefficient == nfrc_ext_dup.film_coefficient == 26
    assert nfrc_ext.emissivity == nfrc_ext_dup.emissivity == 1
    assert nfrc_ext.radiant_temperature == nfrc_ext_dup.radiant_temperature == -18
    assert nfrc_ext.heat_flux == nfrc_ext_dup.heat_flux == 0
    assert nfrc_ext.relative_humidity == nfrc_ext_dup.relative_humidity == 0.5


def test_extract_all_from_xml_file():
    """Test the initialization of conditions from a file."""
    lbnl_con_file = './tests/assets/xml/BoundaryConditionsSteadyState.xml'
    conditions = SteadyState.extract_all_from_xml_file(lbnl_con_file)

    assert len(conditions) == 9
    for con in conditions:
        assert isinstance(con, SteadyState)
