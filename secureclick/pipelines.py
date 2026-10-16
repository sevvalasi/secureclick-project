"""Eğitim ve servis tarafının ortak kullandığı scikit-learn bileşenleri.

Pipeline'lar joblib ile kaydedildiğinde bu modüldeki sınıflara referans verir; bu yüzden
hem ml/ betikleri hem de API aynı tanımları buradan içe aktarır.
"""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline, make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.svm import LinearSVC

from secureclick.features.text_features import TEXT_FEATURE_NAMES, extract_text_features, normalize_tr
from secureclick.features.url_features import FEATURE_NAMES, extract_url_features, normalize_url


class UrlFeatureExtractor(BaseEstimator, TransformerMixin):
    """Ham URL listesi -> el yapımı sözcüksel özellik matrisi."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return np.array([[extract_url_features(u)[k] for k in FEATURE_NAMES] for u in X], dtype=float)

    def get_feature_names_out(self, input_features=None):
        return np.array(FEATURE_NAMES)


class TextFeatureExtractor(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return np.array([[extract_text_features(t)[k] for k in TEXT_FEATURE_NAMES] for t in X], dtype=float)


def _normalize_urls(X):
    return [normalize_url(u) for u in X]


def _normalize_texts(X):
    return [normalize_tr(t) for t in X]


def char_tfidf() -> TfidfVectorizer:
    # URLNet'teki karakter düzeyi temsil fikrinin hafif, doğrusal karşılığı
    return TfidfVectorizer(analyzer="char", ngram_range=(3, 5), min_df=3, max_features=300_000,
                           sublinear_tf=True, dtype=np.float32)


# ---------------------------------------------------------------- URL modelleri
def url_random_forest(n_estimators=300, max_depth=None, min_samples_leaf=1, **_) -> Pipeline:
    return make_pipeline(UrlFeatureExtractor(), RandomForestClassifier(
        n_estimators=n_estimators, max_depth=max_depth, min_samples_leaf=min_samples_leaf,
        n_jobs=-1, random_state=42, class_weight="balanced"))


def url_gradient_boosting(learning_rate=0.1, max_iter=300, max_leaf_nodes=31, **_) -> Pipeline:
    return make_pipeline(UrlFeatureExtractor(), HistGradientBoostingClassifier(
        learning_rate=learning_rate, max_iter=max_iter, max_leaf_nodes=max_leaf_nodes,
        early_stopping=True, random_state=42))


def url_svm(C=0.5, **_) -> Pipeline:
    # LinearSVC olasılık vermez; sigmoid kalibrasyonla olasılığa çevrilir.
    return Pipeline([
        ("norm", FunctionTransformer(_normalize_urls)),
        ("tfidf", char_tfidf()),
        ("clf", CalibratedClassifierCV(LinearSVC(C=C, dual="auto", max_iter=5000), method="sigmoid", cv=3)),
    ])


def url_tfidf_lr(C=4.0, **_) -> Pipeline:
    return Pipeline([
        ("norm", FunctionTransformer(_normalize_urls)),
        ("tfidf", char_tfidf()),
        ("clf", LogisticRegression(C=C, max_iter=3000, solver="liblinear")),
    ])


URL_MODELS = {
    "random_forest": (url_random_forest, {"n_estimators": [200, 400], "min_samples_leaf": [1, 2]}),
    "gradient_boosting": (url_gradient_boosting, {"learning_rate": [0.05, 0.1], "max_leaf_nodes": [31, 63]}),
    "svm": (url_svm, {"C": [0.25, 1.0]}),
    "tfidf_lr": (url_tfidf_lr, {"C": [2.0, 8.0]}),
}

URL_MODEL_LABELS = {
    "blacklist": "Kara Liste (temel çizgi)",
    "random_forest": "Random Forest",
    "gradient_boosting": "Gradient Boosting",
    "svm": "SVM (karakter n-gram)",
    "tfidf_lr": "TF-IDF + Lojistik Regresyon",
    "ensemble": "SecureClick Topluluk (RF + SVM)",
}


# ---------------------------------------------------------------- Metin modelleri
def text_tfidf_lr(C=4.0, **_) -> Pipeline:
    words = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)  # 1-gram + 2-gram
    chars = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True)
    return Pipeline([
        ("feats", FeatureUnion([
            ("tfidf", Pipeline([("norm", FunctionTransformer(_normalize_texts)),
                                ("u", FeatureUnion([("w", words), ("c", chars)]))])),
            ("hand", Pipeline([("x", TextFeatureExtractor()), ("s", StandardScaler())])),
        ])),
        ("clf", LogisticRegression(C=C, max_iter=3000, class_weight="balanced")),
    ])


def text_svm(C=0.5, **_) -> Pipeline:
    p = text_tfidf_lr()
    p.steps[-1] = ("clf", CalibratedClassifierCV(LinearSVC(C=C, dual="auto", max_iter=5000,
                                                           class_weight="balanced"), cv=3))
    return p


TEXT_MODELS = {
    "text_tfidf_lr": (text_tfidf_lr, {"C": [1.0, 4.0, 16.0]}),
    "text_svm": (text_svm, {"C": [0.1, 0.5, 2.0]}),
}
