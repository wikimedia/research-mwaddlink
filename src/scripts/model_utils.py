import xgboost

number_of_features_v1 = 6


def get_model_version(model: xgboost.XGBClassifier) -> str:
    # We should ideally set the model versions in the training pipelines.
    if model.get_booster().num_features() == number_of_features_v1:
        return "v1"
    else:
        return "v2"
