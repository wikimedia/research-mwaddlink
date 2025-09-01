import pytest
import numpy as np
from unittest.mock import MagicMock


@pytest.fixture
def model():
    booster = MagicMock()
    booster.num_features.return_value = 7

    model = MagicMock()
    model.get_booster.return_value = booster

    model.predict_proba.return_value = np.array([[0.1, 0.9]])
    return model
