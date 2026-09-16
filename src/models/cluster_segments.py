"""Chapter: segmenting institutions with unsupervised learning, as an
exploratory complement to the Carnegie Classification rather than a
replacement for it.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


@dataclass
class ClusterResult:
    model: KMeans
    scaler: StandardScaler
    labels: pd.Series
    assignments: pd.DataFrame


def cluster_institutions(
    panel: pd.DataFrame, feature_cols: list[str], n_clusters: int = 4, random_state: int = 42
) -> ClusterResult:
    data = panel.dropna(subset=feature_cols).copy()
    if data.empty:
        raise ValueError("No rows remain after dropping missing features.")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(data[feature_cols])

    model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = model.fit_predict(X_scaled)

    assignments = data[["unitid", "survey_year"]].copy()
    assignments["cluster"] = labels

    return ClusterResult(
        model=model,
        scaler=scaler,
        labels=pd.Series(labels, index=data.index),
        assignments=assignments,
    )


def cluster_profile(
    cluster_result: ClusterResult, panel: pd.DataFrame, feature_cols: list[str]
) -> pd.DataFrame:
    """Mean feature values per cluster, useful for labeling each segment
    (e.g. "large public research", "small tuition-dependent private").
    """
    merged = panel.merge(cluster_result.assignments, on=["unitid", "survey_year"])
    return merged.groupby("cluster")[feature_cols].mean()
