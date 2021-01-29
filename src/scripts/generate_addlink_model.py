#!/usr/bin/env python
# coding: utf-8

import xgboost
from sklearn import model_selection
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import LabelEncoder
import os
import pandas as pd
import sys
import multiprocessing
import subprocess

##################
# This script can be used on any language

if len(sys.argv) >= 2:
    wiki_id = sys.argv[1]
else:
    wiki_id = "enwiki"

##################
# Read the training dataset
df = pd.read_csv(
    "../../data/{0}/training/link_train.csv".format(wiki_id),
    sep="\t",
    header=None,
    quoting=3,
)

# load data
dataset = df.values

# split data into X and y (features and labels)
X = dataset[:, 3:-1]
Y = dataset[:, -1] * 1

# encode string class values as integers
label_encoder = LabelEncoder()
label_encoder = label_encoder.fit(Y)
label_encoded_y = label_encoder.transform(Y)

# Generate a random Train/Test split
# note: the dataset is large enough to avoid Cross Validation
seed = 7
test_size = 0.33
X_train, X_test, y_train, y_test = model_selection.train_test_split(
    X, label_encoded_y, test_size=test_size, random_state=seed
)

# Fit model to the training data
n_cpus_max = min([int(multiprocessing.cpu_count() / 4), 8])
model = xgboost.XGBClassifier(n_jobs=n_cpus_max)
model.fit(X_train, y_train)
print(model)


# make predictions for all test data
y_pred = model.predict(X_test)
predictions = [round(value) for value in y_pred]

# evaluate predictions
predictions = model.predict_proba(X_test)[:, 1]
print("ROC AUC=%.3f" % roc_auc_score(y_test, predictions))

# save the model
data_dir = "../../data/%s" % wiki_id
link_model_filename = "%s.linkmodel.json" % wiki_id
link_model_path = "%s/%s" % (data_dir, link_model_filename)
model.save_model(os.path.realpath(link_model_path))
with open("%s.checksum" % link_model_path, "wb") as checksum_file:
    shasum = subprocess.Popen(
        ["shasum", "-a", "256", "%s" % link_model_filename],
        stdout=subprocess.PIPE,
        cwd=os.path.relpath(data_dir),
    )
    checksum_file.writelines(shasum.stdout)
    checksum_file.close()
