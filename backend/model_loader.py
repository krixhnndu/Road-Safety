"""
model_loader.py
Loads the two trained models (Random Forest, Gradient Boosting) from /models.

This is a 1:1 port of `load_models()` from the original unified_platform.py,
including the runtime unpickling shim needed for a scikit-learn version
mismatch affecting the Gradient Boosting model's internal loss object.
"""
import os
import sys
import joblib

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")


def _apply_sklearn_compat_shim():
    """Runtime unpickle namespace alias hook for scikit-learn version mismatch
    in the Gradient Boosting model (ported verbatim from unified_platform.py)."""
    try:
        import sklearn._loss
        import sklearn._loss.loss as l
        sys.modules['sklearn._loss'].CyHalfMultinomialLoss = l.CyHalfMultinomialLoss
        sys.modules['_loss'] = sys.modules['sklearn._loss']

        def reconstruct(cls, checksum, state):
            return l.CyHalfMultinomialLoss(n_classes=4)

        sys.modules['sklearn._loss'].__pyx_unpickle_CyHalfMultinomialLoss = reconstruct
        sys.modules['_loss'].__pyx_unpickle_CyHalfMultinomialLoss = reconstruct
    except Exception:
        pass


def load_models():
    """Returns (rf_model, gb_model). Either may be None if loading fails."""
    _apply_sklearn_compat_shim()
    try:
        rf = joblib.load(os.path.join(MODELS_DIR, "random_forest_model.pkl"))
    except Exception as e:
        print(f"[model_loader] Failed to load Random Forest model: {e}")
        rf = None
    try:
        gb = joblib.load(os.path.join(MODELS_DIR, "gradient_boosting_model.pkl"))
    except Exception as e:
        print(f"[model_loader] Failed to load Gradient Boosting model: {e}")
        gb = None
    return rf, gb
