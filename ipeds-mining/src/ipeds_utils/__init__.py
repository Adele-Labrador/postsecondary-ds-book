"""Shared utilities for *Mining IPEDS Data*.

One import surface for every notebook in the guidebook, so that a parsing quirk is
fixed once rather than twelve times.

    from ipeds_utils import (
        fetch, read_csv, read_dict, read_intro, assert_reference_period,
        lock_schema, validate, Rule, suppress, synthetic_id,
    )
"""

from .deidentify import coarsen, k_anonymity, suppress, synthetic_id
from .dictionary import (
    assert_reference_period,
    imputation_partner,
    read_dict,
    read_intro,
    read_valuesets,
)
from .features import (
    COLUMN_SOURCES,
    COMPANIONS,
    PEER_FEATURES,
    balanced,
    institution_table,
    load_companion,
    peer_feature_matrix,
    salary_equity,
    stack_vintages,
    tenure_density,
)
from .fetch import (
    DATA_URL,
    DICT_URL,
    FetchError,
    fetch,
    unzip_csv,
    unzip_dict,
    write_provenance,
)
from .io import curated_path, read_curated, write_curated
from .schema import (
    IPEDS_ENCODING,
    IPEDS_ENCODINGS,
    MISSING_MARKERS,
    STRING_CODES,
    code_key,
    decode,
    imputation_summary,
    lock_schema,
    read_csv,
    split_imputation_flags,
)
from .stats import (
    bootstrap_ci,
    cliffs_delta,
    fit_beta_binomial,
    robust_z,
    shrink,
    within_transform,
)
from .validate import (
    Report,
    Rule,
    in_range,
    not_null,
    referential,
    rolls_up,
    subset_of,
    sums_to,
    unique_key,
    validate,
)

__version__ = "1.1.0"

__all__ = [
    "DATA_URL",
    "DICT_URL",
    "FetchError",
    "fetch",
    "unzip_csv",
    "unzip_dict",
    "write_provenance",
    "assert_reference_period",
    "imputation_partner",
    "read_dict",
    "read_intro",
    "read_valuesets",
    "IPEDS_ENCODING",
    "IPEDS_ENCODINGS",
    "decode",
    "imputation_summary",
    "lock_schema",
    "read_csv",
    "split_imputation_flags",
    "Report",
    "Rule",
    "in_range",
    "not_null",
    "referential",
    "subset_of",
    "sums_to",
    "unique_key",
    "validate",
    "coarsen",
    "k_anonymity",
    "suppress",
    "synthetic_id",
    "curated_path",
    "write_curated",
    "read_curated",
    "rolls_up",
    "STRING_CODES",
    "MISSING_MARKERS",
    "code_key",
    "COLUMN_SOURCES",
    "COMPANIONS",
    "balanced",
    "institution_table",
    "load_companion",
    "PEER_FEATURES",
    "peer_feature_matrix",
    "salary_equity",
    "stack_vintages",
    "tenure_density",
    "bootstrap_ci",
    "cliffs_delta",
    "fit_beta_binomial",
    "robust_z",
    "shrink",
    "within_transform",
    "__version__",
]
