#!/usr/bin/env python
# coding: utf-8

import xgboost
from sklearn import model_selection
from sklearn.metrics import accuracy_score
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import LabelEncoder
import pandas as pd
import sys

##################
# This script can be used on any language
# TODO: Add a LANG parameter

if len(sys.argv) >= 2:
    lang = sys.argv[1]
else:
    lang = 'en'

wiki   = lang+'wiki'
##################
# Read the training dataset
df = pd.read_csv('../data/{0}/training/link_train.csv'.format(lang), names= ['page', 'form', 'candidate', 'gram', 'freq', 'ambig', 'kur', 'w2v', 'nav', 'label'], sep = '\t', header = None)

# load data
dataset = df.values

# split data into X and y (features and labels)
X = dataset[:,3:-1]
Y = dataset[:,-1]*1

# encode string class values as integers
label_encoder = LabelEncoder()
label_encoder = label_encoder.fit(Y)
label_encoded_y = label_encoder.transform(Y)

# Generate a random Train/Test split
# note: the dataset is large enough to avoid Cross Validation
seed = 7
test_size = 0.33
X_train, X_test, y_train, y_test = model_selection.train_test_split(X, label_encoded_y, test_size=test_size, random_state=seed)

# Fit model to the training data
model = xgboost.XGBClassifier()
model.fit(X_train, y_train)
print(model)


# make predictions for all test data
y_pred = model.predict(X_test)
predictions = [round(value) for value in y_pred]

# evaluate predictions
predictions = model.predict_proba(X_test)[:, 1]
print('ROC AUC=%.3f' % roc_auc_score(y_test,predictions))

# save the model
model.save_model('../data/{0}/0001.link.bin'.format(lang))

