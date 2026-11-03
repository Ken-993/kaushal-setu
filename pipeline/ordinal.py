"""Frank & Hall (2001) ordinal classifier: K ordered classes -> K-1 binary
problems 'is y > k?', each a logistic regression (so every piece is inspectable).

Also holds picklable helper functions used inside sklearn pipelines. They live in
a real module (not a lambda / __main__) so joblib can reload them in the API.
"""
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.linear_model import LogisticRegression


def split_pipe(text: str) -> list[str]:
    return [t for t in str(text).split("|") if t]


class OrdinalLogit(BaseEstimator, ClassifierMixin):
    def __init__(self, C: float = 1.0, max_iter: int = 2000):
        self.C = C
        self.max_iter = max_iter

    def fit(self, X, y):
        y = np.asarray(y).astype(int)
        self.classes_ = np.arange(y.max() + 1)
        self.models_ = []
        for k in range(len(self.classes_) - 1):
            m = LogisticRegression(C=self.C, max_iter=self.max_iter)
            m.fit(X, (y > k).astype(int))
            self.models_.append(m)
        return self

    def predict_proba(self, X):
        # P(y>k) for k = 0..K-2
        gt = np.column_stack([m.predict_proba(X)[:, 1] for m in self.models_])
        n, K = gt.shape[0], len(self.classes_)
        P = np.zeros((n, K))
        P[:, 0] = 1 - gt[:, 0]
        for k in range(1, K - 1):
            P[:, k] = gt[:, k - 1] - gt[:, k]
        P[:, K - 1] = gt[:, K - 2]
        P = np.clip(P, 1e-9, None)  # cumulative models can cross slightly; clip then renormalise
        return P / P.sum(axis=1, keepdims=True)

    def predict(self, X):
        return self.predict_proba(X).argmax(axis=1)
