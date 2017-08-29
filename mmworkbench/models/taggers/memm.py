# -*- coding: utf-8 -*-
"""
This module contains the Memm entity recognizer.
"""
from __future__ import print_function, absolute_import, unicode_literals, division

from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_selection import SelectFromModel, SelectPercentile
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder as SKLabelEncoder, MaxAbsScaler, StandardScaler

from .taggers import Tagger, START_TAG
from ..helpers import extract_sequence_features

import logging
logger = logging.getLogger(__name__)


class MemmModel(Tagger):
    """A maximum-entropy Markov model."""
    def fit(self, X, y):
        self._clf.fit(X, y)
        return self

    def set_params(self, **parameters):
        self._clf = LogisticRegression()
        self._clf.set_params(**parameters)
        return self

    def get_params(self, deep=True):
        return self._clf.get_params()

    def predict(self, X):
        return self._clf.predict(X)

    def process_and_predict(self, examples, config, resources):
        return [self._predict_example(example, config, resources) for example in examples]

    def _predict_example(self, example, config, resources):
        features_by_segment = self.extract_example_features(example, config, resources)
        if len(features_by_segment) == 0:
            return []
            # return self._label_encoder.decode([], examples=[example])[0]

        predicted_tags = []
        prev_tag = START_TAG
        for features in features_by_segment:
            features['prev_tag'] = prev_tag
            X, _ = self.preprocess_data([features])
            prediction = self.predict(X)
            predicted_tag = self.class_encoder.inverse_transform(prediction)[0]
            predicted_tags.append(predicted_tag)
            prev_tag = predicted_tag

        return predicted_tags
        # return self._label_encoder.decode([predicted_tags], examples=[example])[0]

    def extract_example_features(self, example, config, resources):
        """Extracts feature dicts for each token in an example.

        Args:
            example (mmworkbench.core.Query): an query
        Returns:
            (list dict): features
        """
        return extract_sequence_features(example, config.example_type, config.features, resources)

    def extract_features(self, examples, config, resources, y=None, fit=True):
        """Transforms a list of examples into a feature matrix.

        Args:
            examples (list): The examples.

        Returns:
            (numpy.matrix): The feature matrix.
            (numpy.array): The group labels for examples.
        """
        groups = []
        X = []
        y_offset = 0
        for i, example in enumerate(examples):
            features_by_segment = self.extract_example_features(example, config,
                                                                resources)
            X.extend(features_by_segment)
            groups.extend([i for _ in features_by_segment])
            for j, segment in enumerate(features_by_segment):
                if j == 0:
                    segment['prev_tag'] = START_TAG
                elif fit:
                    segment['prev_tag'] = y[y_offset + j - 1]

            y_offset += len(features_by_segment)
        X, y = self.preprocess_data(X, y, fit)
        return X, y, groups

    def _get_feature_selector(self, selector_type):
        """Get a feature selector instance based on the feature_selector model
        parameter

        Returns:
            (Object): a feature selector which returns a reduced feature matrix,
                given the full feature matrix, X and the class labels, y
        """
        selector = {'l1': SelectFromModel(LogisticRegression(penalty='l1', C=1)),
                    'f': SelectPercentile()}.get(selector_type)
        return selector

    def _get_feature_scaler(self, scale_type):
        """Get a feature value scaler based on the model settings"""
        scaler = {'std-dev': StandardScaler(with_mean=False),
                  'max-abs': MaxAbsScaler()}.get(scale_type)
        return scaler

    def setup_model(self, selector_type, scale_type):
        self.class_encoder = SKLabelEncoder()
        self.feat_vectorizer = DictVectorizer()
        self._feat_selector = self._get_feature_selector(selector_type)
        self._feat_scaler = self._get_feature_scaler(scale_type)

    def preprocess_data(self, X, y=None, fit=False):
        if fit:
            y = self.class_encoder.fit_transform(y)
            X = self.feat_vectorizer.fit_transform(X)
            if self._feat_scaler is not None:
                X = self._feat_scaler.fit_transform(X)
            if self._feat_selector is not None:
                X = self._feat_selector.fit_transform(X, y)
        else:
            X = self.feat_vectorizer.transform(X)
            if self._feat_scaler is not None:
                X = self._feat_scaler.transform(X)
            if self._feat_selector is not None:
                X = self._feat_selector.transform(X)

        return X, y
