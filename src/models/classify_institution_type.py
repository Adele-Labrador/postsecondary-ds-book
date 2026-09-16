"""Chapter: classifying institution type (control/level/Carnegie class)
from operational features.

Baseline-first, per the book's chapter notebook contract: a logistic
regression / small tree ensemble that is easy to interpret for a
policy-facing audience, before any more complex model.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


@dataclass
class ClassificationResult:
    model: RandomForestClassifier
    label_encoder: LabelEncoder
    accuracy: float
    report: str
    test_index: pd.Index


def train_institution_classifier(
    panel: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "carnegie_basic",
    test_size: float = 0.25,
    random_state: int = 42,
) -> ClassificationResult:
    """Fit a random-forest classifier predicting ``target_col`` from
    ``feature_cols``. Rows with a missing target are dropped.
    """
    data = panel.dropna(subset=[target_col] + feature_cols)
    if data.empty:
        raise ValueError("No rows remain after dropping missing target/features.")

    encoder = LabelEncoder()
    y = encoder.fit_transform(data[target_col])
    X = data[feature_cols]

    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, data.index, test_size=test_size, random_state=random_state, stratify=y
    )

    model = RandomForestClassifier(n_estimators=200, random_state=random_state)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    report = classification_report(y_test, preds, target_names=encoder.classes_, zero_division=0)

    return ClassificationResult(
        model=model, label_encoder=encoder, accuracy=acc, report=report, test_index=idx_test
    )
