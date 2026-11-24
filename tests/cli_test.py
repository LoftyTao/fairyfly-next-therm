"""Test cli modules."""
from click.testing import CliRunner
import os

from fairyfly_next_therm.cli.translate import model_to_thmz_cli


def test_model_to_thmz():
    """Test the CLI translation to THMZ."""
    runner = CliRunner()
    input_model = './tests/assets/json/TestModel.ffjson'

    result = runner.invoke(model_to_thmz_cli, [input_model])
    assert result.exit_code == 0

    output_model = './tests/assets/json/TestModel.thmz'
    result = runner.invoke(
        model_to_thmz_cli, [input_model, '--output-file', output_model])
    assert result.exit_code == 0
    assert os.path.isfile(output_model)
    os.remove(output_model)
