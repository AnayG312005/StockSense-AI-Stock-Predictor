import os
import time
import io
import inspect
import logging
import warnings
import contextlib
import datetime as dt
import json
import re
import random
import requests
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import yfinance as yf
from sklearn.preprocessing import MinMaxScaler
from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for, session, make_response
from functools import wraps
from tensorflow.keras.models import load_model
from openai import OpenAI
from tensorflow.keras.layers import InputLayer
from dotenv import load_dotenv

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

# =================================================
# BASIC APP SETUP
# =================================================
load_dotenv()

STATIC_DIR = os.getenv("STATIC_DIR", "static")
MODEL_PATH = os.getenv("MODEL_PATH", "stock_price_prediction.keras")
DEFAULT_STOCK = os.getenv("DEFAULT_STOCK", "RELIANCE.NS")
PREDICTION_WINDOW = int(os.getenv("PREDICTION_WINDOW", "100"))
START_DATE = os.getenv("START_DATE", "2010-01-01")

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.secret_key = os.getenv("SESSION_SECRET", os.urandom(24))

model = None

# =================================================
# CLERK AUTH CONFIG
# =================================================
# Auto-detect correct keys regardless of which env var they were stored in
def _resolve_clerk_keys():
    raw_a = os.getenv("CLERK_PUBLISHABLE_KEY", "")
    raw_b = os.getenv("CLERK_SECRET_KEY", "")
    pk = ""
    sk = ""
    for c in [raw_a, raw_b]:
        # Handle "KEY_NAME=value" format stored in secret value
        val = c.split("=", 1)[1] if "=" in c and not c.startswith("pk_") and not c.startswith("sk_") else c
        if val.startswith("pk_test_") or val.startswith("pk_live_"):
            pk = val
        elif val.startswith("sk_test_") or val.startswith("sk_live_"):
            sk = val
    return pk, sk

CLERK_PUBLISHABLE_KEY, CLERK_SECRET_KEY = _resolve_clerk_keys()

def _get_clerk_frontend_api():
    import base64
    pk = CLERK_PUBLISHABLE_KEY
    for prefix in ("pk_test_", "pk_live_"):
        if pk.startswith(prefix):
            domain = pk[len(prefix):]
            # Strip trailing $ and any digits after it (padding artifacts)
            import re
            domain = re.sub(r'\$\d*$', '', domain)
            try:
                # Pad to multiple of 4
                pad = (4 - len(domain) % 4) % 4
                decoded = base64.b64decode(domain + "=" * pad).decode("utf-8").strip("\x00").strip()
                # Clerk appends $<version> to the domain — strip it
                if "$" in decoded:
                    decoded = decoded[:decoded.index("$")]
                if decoded:
                    return decoded
            except Exception:
                pass
    return "clerk.accounts.dev"

CLERK_FRONTEND_API = _get_clerk_frontend_api()

_clerk_jwks_cache = {"keys": None, "fetched_at": 0}

def _get_clerk_jwks():
    now = time.time()
    if _clerk_jwks_cache["keys"] and now - _clerk_jwks_cache["fetched_at"] < 3600:
        return _clerk_jwks_cache["keys"]
    try:
        url = f"https://{CLERK_FRONTEND_API}/.well-known/jwks.json"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            _clerk_jwks_cache["keys"] = resp.json().get("keys", [])
            _clerk_jwks_cache["fetched_at"] = now
            return _clerk_jwks_cache["keys"]
    except Exception as e:
        print(f"JWKS fetch error: {e}")
    return []

def _verify_clerk_token(token):
    if not token or not JWT_AVAILABLE:
        return None
    try:
        from jwt.algorithms import RSAAlgorithm
        keys = _get_clerk_jwks()
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        matching = next((k for k in keys if k.get("kid") == kid), None) if kid else (keys[0] if keys else None)
        if not matching:
            return None
        public_key = RSAAlgorithm.from_jwk(json.dumps(matching))
        payload = jwt.decode(token, public_key, algorithms=["RS256"], options={"verify_exp": True})
        return payload
    except Exception as e:
        print(f"Token verification error: {e}")
        return None

def get_current_user():
    token = request.cookies.get("__session") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        return _verify_clerk_token(token)
    return None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

# Reduce console noise from yfinance / urllib3
warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("matplotlib").setLevel(logging.ERROR)

# =================================================
# KERAS / INPUTLAYER PATCH
# Helps with old/new Keras config mismatches
# =================================================
_original_inputlayer_init = InputLayer.__init__
_original_inputlayer_sig = inspect.signature(_original_inputlayer_init)

def _patched_inputlayer_init(self, *args, **kwargs):
    kwargs.pop("optional", None)

    batch_shape = kwargs.pop("batch_shape", None)
    batch_input_shape = kwargs.pop("batch_input_shape", None)

    if batch_shape is None and batch_input_shape is not None:
        batch_shape = batch_input_shape

    if batch_shape is not None:
        batch_shape = tuple(batch_shape)

        if "batch_input_shape" in _original_inputlayer_sig.parameters:
            kwargs.setdefault("batch_input_shape", batch_shape)
        elif "batch_shape" in _original_inputlayer_sig.parameters:
            kwargs.setdefault("batch_shape", batch_shape)
        elif "shape" in _original_inputlayer_sig.parameters:
            if len(batch_shape) >= 2:
                kwargs.setdefault("shape", tuple(batch_shape[1:]))
            else:
                kwargs.setdefault("shape", batch_shape)

    return _original_inputlayer_init(self, *args, **kwargs)

InputLayer.__init__ = _patched_inputlayer_init

# =================================================
# MODEL LOADING
# =================================================
def load_stock_model():
    global model

    if not os.path.exists(MODEL_PATH):
        print(f"⚠ Model file not found: {MODEL_PATH}")
        model = None
        return

    load_attempts = [
        {"compile": False, "safe_mode": False},
        {"compile": False},
        {"compile": True, "safe_mode": False},
        {"compile": True},
    ]

    for kwargs in load_attempts:
        try:
            # Some Keras versions accept safe_mode, some do not
            try:
                sig = inspect.signature(load_model)
                if "safe_mode" not in sig.parameters:
                    kwargs = {k: v for k, v in kwargs.items() if k != "safe_mode"}
            except Exception:
                kwargs = {k: v for k, v in kwargs.items() if k != "safe_mode"}

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                model = load_model(MODEL_PATH, **kwargs)

            print("✅ Model loaded successfully")
            return

        except Exception as e:
            print(f"⚠ Model load attempt failed with {kwargs}: {e}")

    print("❌ Model could not be loaded. App will run with fallback prediction only.")
    model = None

load_stock_model()

# =================================================
# YFINANCE HELPERS
# =================================================
def _silence_output(fn, *args, **kwargs):
    """Run noisy functions quietly."""
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
        return fn(*args, **kwargs)

def normalize_stock_symbol(symbol: str) -> str:
    symbol = (symbol or "").strip().upper()
    symbol = symbol.replace(" ", "")
    return symbol

def build_symbol_candidates(stock: str):
    """
    Creates a small, sensible fallback list for Indian tickers.
    Example:
        RELIANCE.NS -> RELIANCE.NS, RELIANCE.BO, RELIANCE
        RELIANCE    -> RELIANCE, RELIANCE.NS, RELIANCE.BO
    """
    stock = normalize_stock_symbol(stock)
    if not stock:
        return []

    candidates = [stock]

    if "." in stock:
        base, suffix = stock.rsplit(".", 1)
        if suffix == "NS":
            candidates.extend([f"{base}.BO", base])
        elif suffix == "BO":
            candidates.extend([f"{base}.NS", base])
        else:
            candidates.extend([base, f"{base}.NS", f"{base}.BO"])
    else:
        candidates.extend([f"{stock}.NS", f"{stock}.BO"])

    # De-duplicate while preserving order
    seen = set()
    out = []
    for x in candidates:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out

def fetch_yf_once(symbol: str, start: str = START_DATE):
    """
    Fetch using yfinance quietly.
    Tries Ticker.history first, then download as a backup.
    """
    end = dt.datetime.now()

    # Attempt 1: Ticker.history
    try:
        ticker = yf.Ticker(symbol)
        df = _silence_output(
            ticker.history,
            start=start,
            end=end,
            auto_adjust=True,
            actions=False,
            interval="1d"
        )
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
    except Exception:
        pass

    # Attempt 2: yf.download backup
    try:
        df = _silence_output(
            yf.download,
            symbol,
            start=start,
            end=end,
            progress=False,
            threads=False,
            auto_adjust=True,
            group_by="column"
        )
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
    except Exception:
        pass

    return None

def fetch_stock_data(stock: str, retries: int = 2, sleep_seconds: float = 0.75):
    """
    Tries multiple symbol variants quietly until one returns data.
    Returns: (df, resolved_symbol)
    """
    stock = normalize_stock_symbol(stock) or DEFAULT_STOCK
    candidates = build_symbol_candidates(stock)

    # For common Indian names, add a few helpful extra options if the user enters a bare name.
    extra_map = {
        "RELIANCE": ["RELIANCE.NS", "RELIANCE.BO"],
        "TCS": ["TCS.NS", "TCS.BO"],
        "INFY": ["INFY.NS", "INFY.BO"],
        "SBIN": ["SBIN.NS", "SBIN.BO"],
        "HDFCBANK": ["HDFCBANK.NS", "HDFCBANK.BO"],
        "ICICIBANK": ["ICICIBANK.NS", "ICICIBANK.BO"],
    }
    if stock in extra_map:
        for s in extra_map[stock]:
            if s not in candidates:
                candidates.append(s)

    last_error = None

    for candidate in candidates:
        for attempt in range(1, retries + 1):
            try:
                df = fetch_yf_once(candidate)
                if df is not None and not df.empty:
                    return df, candidate
            except Exception as e:
                last_error = e

            time.sleep(sleep_seconds)

    if last_error is not None:
        print(f"⚠ Final data fetch error for {stock}: {last_error}")

    return None, stock

# =================================================
# DATAFRAME / SERIES HELPERS
# =================================================
def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    df = df.copy()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            "_".join([str(x) for x in col if str(x) != ""]).strip()
            for col in df.columns.values
        ]

    return df

def extract_close_series(df: pd.DataFrame):
    if df is None or df.empty:
        return None

    df = normalize_dataframe_columns(df)

    if "Close" not in df.columns:
        for col in df.columns:
            if str(col).lower() == "close":
                df["Close"] = df[col]
                break

    if "Close" not in df.columns:
        return None

    close_raw = df["Close"]
    if isinstance(close_raw, pd.DataFrame):
        close_raw = close_raw.iloc[:, 0]

    close_series = pd.to_numeric(close_raw, errors="coerce").dropna()
    if close_series.empty:
        return None

    return close_series.astype(float)

def create_sequences(data: np.ndarray, window: int = 100):
    x, y = [], []
    for i in range(window, len(data)):
        x.append(data[i - window:i])
        y.append(data[i, 0])
    return np.array(x), np.array(y)

def safe_inverse_scale(values, scaler: MinMaxScaler):
    """
    Returns inverse-transformed values only when they look scaled.
    If they already look like raw prices, returns them unchanged.
    """
    arr = np.asarray(values, dtype=float).reshape(-1)

    if arr.size == 0:
        return arr

    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return arr

    looks_scaled = finite.min() >= -0.25 and finite.max() <= 1.25

    if looks_scaled:
        try:
            return scaler.inverse_transform(arr.reshape(-1, 1)).reshape(-1)
        except Exception:
            return arr

    return arr

def last_n_trend(close_series: pd.Series, n: int = 5):
    close = close_series.dropna()
    if len(close) < 2:
        return 0.0

    n = min(n, len(close) - 1)
    start_price = float(close.iloc[-(n + 1)])
    end_price = float(close.iloc[-1])

    if start_price == 0:
        return 0.0

    return (end_price - start_price) / start_price

def calculate_rsi(close_series: pd.Series, period: int = 14):
    close = close_series.dropna()
    if len(close) < period + 1:
        return None

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()

    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    if rsi.dropna().empty:
        return None
    return float(rsi.iloc[-1])

def calculate_macd(close_series: pd.Series):
    close = close_series.dropna()
    if len(close) < 35:
        return None, None, None

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return float(macd.iloc[-1]), float(signal.iloc[-1]), float(hist.iloc[-1])

# =================================================
# PLOT HELPERS
# =================================================
def save_plot(path, plot_fn):
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(11, 5))
    fig.patch.set_facecolor("#0d1117")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0d1117")
    plot_fn()
    ax.spines["bottom"].set_color("#1e2d3d")
    ax.spines["top"].set_color("#1e2d3d")
    ax.spines["left"].set_color("#1e2d3d")
    ax.spines["right"].set_color("#1e2d3d")
    ax.tick_params(colors="#64748b")
    ax.xaxis.label.set_color("#64748b")
    ax.yaxis.label.set_color("#64748b")
    ax.title.set_color("#94a3b8")
    plt.legend(facecolor="#0d1117", edgecolor="#1e2d3d", labelcolor="#94a3b8")
    plt.tight_layout()
    plt.savefig(path, dpi=150, facecolor="#0d1117")
    plt.close()
    plt.style.use("default")

def ensure_static_dir():
    os.makedirs(STATIC_DIR, exist_ok=True)

# =================================================
# RECOMMENDATION LOGIC
# =================================================
def generate_recommendation(
    close_series: pd.Series,
    predicted_price: float = None,
    model_used: bool = False,
    ema20_last: float = None,
    ema50_last: float = None
):
    close = close_series.dropna().astype(float)

    if close.empty:
        return {
            "action": "HOLD ⏳",
            "confidence": "Low",
            "reason": "Not enough market data is available to make a reliable recommendation.",
            "last_close": None,
            "predicted_price": None,
            "predicted_move_pct": None,
            "trend_pct": None,
        }

    last_close = float(close.iloc[-1])
    recent_trend = float(last_n_trend(close, n=5))

    if predicted_price is None or not np.isfinite(predicted_price):
        predicted_price = last_close * (1 + recent_trend)

    predicted_price = float(predicted_price)

    if last_close == 0:
        predicted_move = 0.0
    else:
        predicted_move = (predicted_price - last_close) / last_close

    ema_bonus = 0.0
    ema_comment = ""

    if ema20_last is not None and ema50_last is not None:
        if ema20_last > ema50_last:
            ema_bonus = 0.004
            ema_comment = "Short-term momentum is above the medium-term trend."
        elif ema20_last < ema50_last:
            ema_bonus = -0.004
            ema_comment = "Short-term momentum is below the medium-term trend."
        else:
            ema_comment = "Short-term and medium-term momentum are balanced."

    rsi = calculate_rsi(close)
    rsi_bonus = 0.0
    rsi_comment = ""

    if rsi is not None:
        if rsi < 30:
            rsi_bonus = 0.003
            rsi_comment = "RSI suggests the stock may be oversold."
        elif rsi > 70:
            rsi_bonus = -0.003
            rsi_comment = "RSI suggests the stock may be overbought."
        else:
            rsi_comment = "RSI is in a neutral zone."

    score = (0.65 * predicted_move) + (0.25 * recent_trend) + ema_bonus + rsi_bonus

    if score > 0.01:
        action = "BUY 📈"
        confidence = "High" if score > 0.03 else "Medium" if score > 0.015 else "Low"
        base_reason = "The stock shows signs of upward momentum."
    elif score < -0.01:
        action = "SELL 📉"
        confidence = "High" if score < -0.03 else "Medium" if score < -0.015 else "Low"
        base_reason = "The stock shows signs of downward pressure."
    else:
        action = "HOLD ⏳"
        confidence = "Low"
        base_reason = "The stock is moving without a strong directional edge."

    trend_text = "upward" if recent_trend > 0 else "downward" if recent_trend < 0 else "sideways"
    model_text = "The model helped shape this view." if model_used else "This view is based on recent market behavior."

    details = [base_reason, f"Recent trend looks {trend_text}."]
    if ema_comment:
        details.append(ema_comment)
    if rsi_comment:
        details.append(rsi_comment)
    details.append(model_text)

    human_reason = " ".join(details)

    return {
        "action": action,
        "confidence": confidence,
        "reason": human_reason,
        "last_close": round(last_close, 2),
        "predicted_price": round(predicted_price, 2),
        "predicted_move_pct": round(predicted_move * 100, 2),
        "trend_pct": round(recent_trend * 100, 2),
        "rsi": None if rsi is None else round(rsi, 2),
    }

# =================================================
# MAIN PROCESSING
# =================================================
def process_prediction(stock_input, template="prediction.html"):
    stock_input = normalize_stock_symbol(stock_input) or DEFAULT_STOCK

    df, resolved_stock = fetch_stock_data(stock_input)

    if df is None or df.empty:
        return render_template(
            template,
            error_message="Stock data unavailable. Please try another ticker.",
            stock_value=stock_input,
            resolved_stock=resolved_stock,
            recommendation=None,
            data_desc=None,
            dataset_link=None,
            plot_path_ema_20_50=None,
            plot_path_ema_100_200=None,
            plot_path_prediction=None
        )

    df = normalize_dataframe_columns(df).dropna(how="all")

    close_series = extract_close_series(df)
    if close_series is None or len(close_series) < max(PREDICTION_WINDOW + 50, 150):
        return render_template(
            template,
            error_message="Not enough valid price data for prediction.",
            stock_value=stock_input,
            resolved_stock=resolved_stock,
            recommendation=None,
            data_desc=None,
            dataset_link=None,
            plot_path_ema_20_50=None,
            plot_path_ema_100_200=None,
            plot_path_prediction=None
        )

    # Keep a compact, readable description table for the UI
    try:
        data_desc = df.describe(include="all").fillna("").to_html(classes="table-auto w-full", border=0)
    except Exception:
        data_desc = None

    # Technical indicators
    ema20 = close_series.ewm(span=20, adjust=False).mean()
    ema50 = close_series.ewm(span=50, adjust=False).mean()
    ema100 = close_series.ewm(span=100, adjust=False).mean()
    ema200 = close_series.ewm(span=200, adjust=False).mean()

    # Train / test split
    close_df = pd.DataFrame(close_series.values, columns=["Close"])
    train_size = int(len(close_df) * 0.7)

    if train_size <= PREDICTION_WINDOW:
        train_size = PREDICTION_WINDOW + 1

    train = close_df.iloc[:train_size].copy()
    test = close_df.iloc[train_size:].copy()

    scaler = MinMaxScaler(feature_range=(0, 1))
    scaler.fit(train)

    # Build the final input block for sequence generation
    past_window = train.tail(PREDICTION_WINDOW)
    final_df = pd.concat([past_window, test], ignore_index=True)

    input_data = scaler.transform(final_df)
    x_test, y_test = create_sequences(input_data, window=PREDICTION_WINDOW)

    y_predicted = None
    y_test_actual = None
    predicted_price = None
    model_used = False

    if model is not None and len(x_test) > 0:
        try:
            x_test_reshaped = x_test.reshape((x_test.shape[0], x_test.shape[1], 1))

            pred_scaled = model.predict(x_test_reshaped, verbose=0)
            y_predicted = safe_inverse_scale(pred_scaled, scaler)
            y_test_actual = safe_inverse_scale(y_test, scaler)

            if y_predicted is not None and len(y_predicted) > 0:
                predicted_price = float(np.asarray(y_predicted).reshape(-1)[-1])
                model_used = True

        except Exception as e:
            print(f"❌ Prediction error: {e}")
            model_used = False
            predicted_price = None

    # Fallback prediction when model fails or is unavailable
    if predicted_price is None:
        recent_trend = last_n_trend(close_series, n=5)
        ema_trend = 0.0
        if len(ema20.dropna()) > 0 and len(ema50.dropna()) > 0:
            ema_trend = (float(ema20.iloc[-1]) - float(ema50.iloc[-1])) / float(close_series.iloc[-1])

        blended_trend = (0.7 * recent_trend) + (0.3 * ema_trend)
        predicted_price = float(close_series.iloc[-1]) * (1 + blended_trend)

    recommendation = generate_recommendation(
        close_series=close_series,
        predicted_price=predicted_price,
        model_used=model_used,
        ema20_last=float(ema20.iloc[-1]) if len(ema20) else None,
        ema50_last=float(ema50.iloc[-1]) if len(ema50) else None,
    )

    ensure_static_dir()

    # Plots
    ema_20_50_path = os.path.join(STATIC_DIR, "ema_20_50.png")
    save_plot(
        ema_20_50_path,
        lambda: (
            plt.plot(close_series.values, label="Close"),
            plt.plot(ema20.values, label="EMA 20"),
            plt.plot(ema50.values, label="EMA 50"),
            plt.title(f"{resolved_stock} - Close vs EMA 20/50"),
            plt.xlabel("Time"),
            plt.ylabel("Price"),
        )
    )

    ema_100_200_path = os.path.join(STATIC_DIR, "ema_100_200.png")
    save_plot(
        ema_100_200_path,
        lambda: (
            plt.plot(close_series.values, label="Close"),
            plt.plot(ema100.values, label="EMA 100"),
            plt.plot(ema200.values, label="EMA 200"),
            plt.title(f"{resolved_stock} - Close vs EMA 100/200"),
            plt.xlabel("Time"),
            plt.ylabel("Price"),
        )
    )

    prediction_path = None
    if y_predicted is not None and y_test_actual is not None and len(y_predicted) > 0 and len(y_test_actual) > 0:
        prediction_path = os.path.join(STATIC_DIR, "prediction.png")
        save_plot(
            prediction_path,
            lambda: (
                plt.plot(np.asarray(y_test_actual).reshape(-1), label="Actual"),
                plt.plot(np.asarray(y_predicted).reshape(-1), label="Predicted"),
                plt.title(f"{resolved_stock} - Actual vs Predicted"),
                plt.xlabel("Time"),
                plt.ylabel("Price"),
            )
        )

    # Save CSV for download
    csv_name = f"{resolved_stock.replace('.', '_')}.csv"
    csv_path = os.path.join(STATIC_DIR, csv_name)

    try:
        df.to_csv(csv_path)
    except Exception as e:
        print(f"⚠ Could not save CSV: {e}")
        csv_name = None

    return render_template(
        template,
        error_message=None,
        stock_value=stock_input,
        resolved_stock=resolved_stock,
        recommendation=recommendation,
        data_desc=data_desc,
        dataset_link=csv_name,
        plot_path_ema_20_50=ema_20_50_path,
        plot_path_ema_100_200=ema_100_200_path,
        plot_path_prediction=prediction_path,
    )

# =================================================
# ROUTES
# =================================================
def _clerk_ctx():
    return {
        "clerk_publishable_key": CLERK_PUBLISHABLE_KEY,
        "clerk_frontend_api": CLERK_FRONTEND_API,
    }

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        return process_prediction(request.form.get("stock"))
    return render_template("home.html", **_clerk_ctx())

@app.route("/prediction", methods=["GET", "POST"])
@require_auth
def prediction():
    if request.method == "POST":
        return process_prediction(request.form.get("stock"))
    return render_template(
        "prediction.html",
        stock_value=DEFAULT_STOCK,
        resolved_stock=DEFAULT_STOCK,
        recommendation=None,
        error_message=None,
        data_desc=None,
        dataset_link=None,
        plot_path_ema_20_50=None,
        plot_path_ema_100_200=None,
        plot_path_prediction=None,
        **_clerk_ctx()
    )

@app.route("/download/<filename>")
def download_file(filename):
    path = os.path.join(STATIC_DIR, filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "File not found", 404

@app.route("/login")
def login_page():
    user = get_current_user()
    if user:
        return redirect(url_for("home"))
    return render_template("login.html",
        clerk_publishable_key=CLERK_PUBLISHABLE_KEY,
        clerk_frontend_api=CLERK_FRONTEND_API)

@app.route("/sso-callback")
def sso_callback():
    return render_template("sso_callback.html",
        clerk_publishable_key=CLERK_PUBLISHABLE_KEY,
        clerk_frontend_api=CLERK_FRONTEND_API)

@app.route("/sentiment")
@require_auth
def sentiment():
    return render_template("sentiment.html", **_clerk_ctx())

@app.route("/risk")
@require_auth
def risk():
    return render_template("risk.html", **_clerk_ctx())

@app.route("/portfolio")
@require_auth
def portfolio():
    return render_template("portfolio.html", **_clerk_ctx())

# =================================================
# REAL-TIME DATA APIs
# =================================================

def _safe_float(v, decimals=2):
    try:
        return round(float(v), decimals) if v is not None and not (isinstance(v, float) and (v != v)) else None
    except:
        return None

def _fetch_live_quote(ticker):
    try:
        tk = yf.Ticker(ticker)
        info = tk.fast_info
        hist = tk.history(period="5d", interval="1d")
        price = _safe_float(getattr(info, "last_price", None))
        prev_close = _safe_float(getattr(info, "previous_close", None))
        change_pct = round((price - prev_close) / prev_close * 100, 2) if price and prev_close else None
        vol = getattr(info, "three_month_average_volume", None)
        last_vol = getattr(info, "last_volume", None)
        rel_vol = round(last_vol / vol, 2) if vol and last_vol and vol > 0 else 1.0
        highs = hist["High"].dropna().tolist()[-5:] if len(hist) >= 2 else []
        lows = hist["Low"].dropna().tolist()[-5:] if len(hist) >= 2 else []
        closes = hist["Close"].dropna().tolist()[-5:] if len(hist) >= 2 else []
        return {
            "ticker": ticker,
            "price": price,
            "prev_close": prev_close,
            "change_pct": change_pct,
            "volume": int(last_vol) if last_vol else None,
            "avg_volume": int(vol) if vol else None,
            "rel_volume": rel_vol,
            "highs": highs,
            "lows": lows,
            "closes": closes,
            "market_cap": getattr(info, "market_cap", None),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

def _compute_risk_score(q):
    score = 0
    rel_vol = q.get("rel_volume", 1.0) or 1.0
    change_pct = abs(q.get("change_pct") or 0)
    closes = q.get("closes", [])
    if rel_vol > 3: score += 30
    elif rel_vol > 2: score += 20
    elif rel_vol > 1.5: score += 10
    if change_pct > 8: score += 30
    elif change_pct > 5: score += 20
    elif change_pct > 3: score += 10
    if len(closes) >= 3:
        std = pd.Series(closes).pct_change().std()
        if std: score += min(int(std * 500), 30)
    if q.get("change_pct", 0) and q["change_pct"] > 0 and rel_vol > 2.5: score += 10
    return min(score, 100)

@app.route("/api/live-ticker")
def api_live_ticker():
    tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "AAPL", "TSLA", "GOOGL", "MSFT", "SBIN.NS", "WIPRO.NS"]
    results = []
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            fi = tk.fast_info
            price = _safe_float(getattr(fi, "last_price", None))
            prev = _safe_float(getattr(fi, "previous_close", None))
            chg = round((price - prev) / prev * 100, 2) if price and prev else 0
            results.append({"ticker": t, "price": price, "change_pct": chg})
        except:
            results.append({"ticker": t, "price": None, "change_pct": 0})
    return jsonify(results)

@app.route("/api/risk-data")
@require_auth
def api_risk_data():
    watchlist = ["TSLA", "ADANIENT.NS", "YESBANK.NS", "RELIANCE.NS", "HDFCBANK.NS", "INFY.NS", "TCS.NS", "SBIN.NS", "AAPL", "WIPRO.NS"]
    results = []
    for t in watchlist:
        q = _fetch_live_quote(t)
        if "error" in q:
            continue
        score = _compute_risk_score(q)
        chg = q.get("change_pct") or 0
        rel_vol = q.get("rel_volume") or 1.0
        if score >= 70: label, badge = "Extreme Risk", "ring-extreme score-extreme"
        elif score >= 50: label, badge = "High Risk", "ring-high score-high"
        elif score >= 30: label, badge = "Moderate", "ring-moderate score-moderate"
        else: label, badge = "Safe", "ring-safe score-safe"
        results.append({
            "ticker": t, "score": score, "label": label, "badge": badge,
            "change_pct": chg, "rel_volume": rel_vol,
            "price": q.get("price"),
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    high_risk = [r for r in results if r["score"] >= 50]
    safe = [r for r in results if r["score"] < 30]
    kpis = {
        "scanned": len(results),
        "high_risk": len(high_risk),
        "anomalies": len([r for r in results if r.get("rel_volume", 1) > 2]),
        "safe": len(safe),
    }
    volatility_series = []
    for r in results[:5]:
        closes = _fetch_live_quote(r["ticker"]).get("closes", [])
        if len(closes) >= 2:
            pct_changes = [abs(closes[i]/closes[i-1]-1)*100 for i in range(1, len(closes))]
            volatility_series.append({"ticker": r["ticker"], "vol": round(sum(pct_changes)/len(pct_changes), 2)})
    sector_heat = []
    sectors = [
        ("Banking", ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS"]),
        ("IT/Tech", ["TCS.NS", "INFY.NS", "WIPRO.NS"]),
        ("Energy", ["RELIANCE.NS"]),
        ("Auto", ["MARUTI.NS", "TATAMOTORS.NS"]),
        ("Adani Group", ["ADANIENT.NS", "ADANIPORTS.NS"]),
    ]
    for sector_name, tickers_list in sectors:
        matched = [r for r in results if r["ticker"] in tickers_list]
        avg_score = round(sum(x["score"] for x in matched) / len(matched), 0) if matched else 50
        sector_heat.append({"name": sector_name, "score": int(avg_score)})
    return jsonify({
        "kpis": kpis, "stocks": results, "high_risk": high_risk[:5],
        "safe": safe[:5], "sector_heat": sector_heat,
        "volatility_series": volatility_series,
    })

@app.route("/api/sentiment-data")
@require_auth
def api_sentiment_data():
    tickers = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "SBIN.NS", "AAPL", "TSLA", "MSFT"]
    bullish = 0
    bearish = 0
    total = 0
    sector_scores = {}
    sector_map = {
        "RELIANCE.NS": "Energy", "TCS.NS": "IT/Tech", "HDFCBANK.NS": "Banking",
        "INFY.NS": "IT/Tech", "SBIN.NS": "Banking", "AAPL": "US Tech",
        "TSLA": "US Tech", "MSFT": "US Tech",
    }
    signals = []
    for t in tickers:
        q = _fetch_live_quote(t)
        if "error" in q:
            continue
        chg = q.get("change_pct") or 0
        total += 1
        if chg > 0.5:
            bullish += 1
        elif chg < -0.5:
            bearish += 1
        sector = sector_map.get(t, "Other")
        sector_scores.setdefault(sector, []).append(chg)
        direction = "positive" if chg > 0 else "negative" if chg < 0 else "neutral"
        signals.append({
            "ticker": t, "change_pct": chg, "price": q.get("price"),
            "direction": direction, "sector": sector,
        })
    bull_pct = round(bullish / total * 100) if total else 68
    bear_pct = round(bearish / total * 100) if total else 32
    neutral_pct = 100 - bull_pct - bear_pct
    if bull_pct > 60: mood, mood_icon, mood_label = "Bullish", "😤", "Bullish"
    elif bear_pct > 50: mood, mood_icon, mood_label = "Bearish", "😰", "Bearish"
    else: mood, mood_icon, mood_label = "Neutral", "😐", "Neutral"
    fg_index = min(100, max(0, round(bull_pct * 1.1 - bear_pct * 0.5)))
    sector_sentiment = []
    for sector, changes in sector_scores.items():
        avg = sum(changes) / len(changes) if changes else 0
        val = min(100, max(0, int(50 + avg * 5)))
        sector_sentiment.append({"name": sector, "val": val, "avg_change": round(avg, 2)})
    history = []
    try:
        bench = yf.Ticker("^NSEI")
        hist = bench.history(period="30d", interval="1d")
        if len(hist) < 5:
            bench = yf.Ticker("SPY")
            hist = bench.history(period="30d", interval="1d")
        closes = hist["Close"].dropna().tolist()
        for i, c in enumerate(closes):
            if i == 0:
                history.append({"bull": 50, "bear": 50})
            else:
                chg = (c - closes[i-1]) / closes[i-1] * 100
                b = min(95, max(5, 50 + chg * 8))
                history.append({"bull": round(b, 1), "bear": round(100-b, 1)})
    except:
        history = [{"bull": 50, "bear": 50}] * 30
    return jsonify({
        "fg_index": fg_index, "mood": mood_label, "mood_icon": mood_icon,
        "bull_pct": bull_pct, "bear_pct": bear_pct, "neutral_pct": neutral_pct,
        "breakdown": {"bullish": bull_pct, "bearish": bear_pct, "neutral": neutral_pct,
                      "panic": max(0, bear_pct - 10), "greed": max(0, bull_pct - 55)},
        "sector_sentiment": sector_sentiment,
        "signals": signals, "history": history,
    })

@app.route("/api/portfolio-data")
@require_auth
def api_portfolio_data():
    holdings = [
        {"ticker": "RELIANCE.NS", "shares": 10, "buy_price": 2400, "sector": "Energy"},
        {"ticker": "TCS.NS", "shares": 5, "buy_price": 3200, "sector": "IT/Tech"},
        {"ticker": "HDFCBANK.NS", "shares": 15, "buy_price": 1450, "sector": "Banking"},
        {"ticker": "INFY.NS", "shares": 12, "buy_price": 1300, "sector": "IT/Tech"},
        {"ticker": "SBIN.NS", "shares": 20, "buy_price": 520, "sector": "Banking"},
    ]
    total_invested = 0
    total_current = 0
    sector_alloc = {}
    stock_data = []
    for h in holdings:
        q = _fetch_live_quote(h["ticker"])
        price = q.get("price") or h["buy_price"]
        invested = h["shares"] * h["buy_price"]
        current = h["shares"] * price
        pl = current - invested
        pl_pct = round(pl / invested * 100, 2) if invested else 0
        total_invested += invested
        total_current += current
        sector = h["sector"]
        sector_alloc[sector] = sector_alloc.get(sector, 0) + current
        score = _compute_risk_score(q)
        stock_data.append({
            "ticker": h["ticker"], "shares": h["shares"],
            "buy_price": h["buy_price"], "current_price": _safe_float(price),
            "invested": round(invested, 2), "current_value": round(current, 2),
            "pl": round(pl, 2), "pl_pct": pl_pct,
            "sector": sector, "risk_score": score,
        })
    total_pl = total_current - total_invested
    total_pl_pct = round(total_pl / total_invested * 100, 2) if total_invested else 0
    sector_list = [{"name": k, "value": round(v, 2), "pct": round(v / total_current * 100, 1)} for k, v in sector_alloc.items()]
    avg_risk = round(sum(s["risk_score"] for s in stock_data) / len(stock_data)) if stock_data else 30
    num_sectors = len(sector_alloc)
    diversification = min(100, num_sectors * 20)
    health = min(100, max(0, round((100 - avg_risk) * 0.6 + diversification * 0.4)))
    projection = []
    base = total_current
    for y in range(11):
        best = round(base * ((1.15) ** y) / 100000, 2)
        base_c = round(base * ((1.10) ** y) / 100000, 2)
        bear = round(base * ((1.05) ** y) / 100000, 2)
        projection.append({"year": 2025 + y, "best": best, "base": base_c, "bear": bear})
    return jsonify({
        "total_invested": round(total_invested, 2),
        "total_current": round(total_current, 2),
        "total_pl": round(total_pl, 2),
        "total_pl_pct": total_pl_pct,
        "health_score": health,
        "avg_risk": avg_risk,
        "diversification": diversification,
        "sector_allocation": sector_list,
        "stocks": stock_data,
        "projection": projection,
        "risk_reward": round((total_pl_pct + 10) / max(avg_risk / 10, 1), 2) if avg_risk else 2.0,
    })

@app.route("/api/copilot", methods=["POST"])
def copilot():
    try:
        data = request.get_json(force=True)
        user_message = (data.get("message") or "").strip()
        stock = (data.get("stock") or "").strip()
        if not user_message:
            return jsonify({"reply": "Please ask a question."})

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        system_prompt = (
            "You are an expert AI stock market trading assistant. "
            "You give concise, clear, and actionable financial insights. "
            "Always include: a brief technical analysis, a risk note, and a clear Buy/Hold/Sell suggestion with reasoning. "
            "Keep responses under 120 words. Use plain language. Do not use markdown headers. "
            "Always add a disclaimer that this is not financial advice."
        )
        if stock:
            system_prompt += f" The user is currently analyzing {stock}."

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=200,
            temperature=0.7,
        )
        reply = response.choices[0].message.content.strip()
        return jsonify({"reply": reply})

    except Exception as e:
        print(f"Copilot error: {e}")
        return jsonify({"reply": "I'm having trouble connecting right now. Please try again in a moment."})

@app.route("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "default_stock": DEFAULT_STOCK,
    }

# =================================================
# RUN APP
# =================================================
if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug_mode = os.getenv("FLASK_DEBUG", "1") == "1"

    app.run(host=host, port=port, debug=debug_mode, use_reloader=False)