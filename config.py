"""Editable jury configuration, persisted to data/jury_config.json and shared
across all cases. Everything is editable; anything unset falls back to the code
defaults, so the jury works out of the box.

Config sections: dimensions, personas, models, source_guidance, output_contract.
The live panel is the CROSS-PRODUCT of models x personas (one juror per pairing).
"""

import os
import json

import dimensions as dim_defaults
import jury

CONFIG_PATH = os.path.join("data", "jury_config.json")

DEFAULT_PERSONAS = [
    {"name": name, "temperature": temp, "text": text, "enabled": True}
    for name, temp, text in jury.DEFAULT_PERSONAS
]
DEFAULT_MODELS = [
    {"provider": "anthropic", "model": "claude-sonnet-4-6", "enabled": True},
    {"provider": "gemini", "model": "gemini-2.5-pro", "enabled": True},
]


def load_raw():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_raw(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def _save_key(key, value):
    cfg = load_raw()
    cfg[key] = value
    save_raw(cfg)


def _reset_key(key):
    cfg = load_raw()
    cfg.pop(key, None)
    save_raw(cfg)


# ------------------------------------------------------------ dimensions
def all_dimension_configs():
    cfg = load_raw()
    if cfg.get("dimensions"):
        return [dict(d) for d in cfg["dimensions"]]
    return [
        {"name": d.name, "description": d.description, "prompt": d.prompt,
         "scale": d.scale, "enabled": True}
        for d in dim_defaults.DEFAULT_DIMENSIONS
    ]


def save_dimensions(dim_list):
    _save_key("dimensions", dim_list)


def reset_dimensions():
    _reset_key("dimensions")


def active_dimensions():
    dims = [
        dim_defaults.Dimension(name=d["name"], description=d.get("description", ""),
                               prompt=d.get("prompt", ""), scale=d.get("scale", "1-5"))
        for d in all_dimension_configs()
        if d.get("enabled", True) and d.get("name") and d.get("prompt")
    ]
    return dims or list(dim_defaults.DEFAULT_DIMENSIONS)


# -------------------------------------------------------------- personas
def all_personas():
    cfg = load_raw()
    return [dict(p) for p in cfg["personas"]] if "personas" in cfg else [dict(p) for p in DEFAULT_PERSONAS]


def save_personas(personas):
    _save_key("personas", personas)


def reset_personas():
    _reset_key("personas")


# ---------------------------------------------------------------- models
def all_models():
    cfg = load_raw()
    if "models" in cfg:
        return [dict(m) for m in cfg["models"]]
    env = os.getenv("JURY_PANEL", "").strip()
    if env:
        out = []
        for spec in env.split(","):
            parts = [p.strip() for p in spec.split(":")]
            if parts and parts[0]:
                out.append({"provider": parts[0], "model": parts[1] if len(parts) > 1 else "",
                            "enabled": True})
        if out:
            return out
    return [dict(m) for m in DEFAULT_MODELS]


def save_models(models):
    _save_key("models", models)


def reset_models():
    _reset_key("models")


# --------------------------------------------------- shared scaffolding
def active_source_guidance():
    return load_raw().get("source_guidance") or dim_defaults.SOURCE_GUIDANCE


def save_source_guidance(text):
    _save_key("source_guidance", text)


def reset_source_guidance():
    _reset_key("source_guidance")


def active_output_contract():
    return load_raw().get("output_contract") or dim_defaults.OUTPUT_CONTRACT


def save_output_contract(text):
    _save_key("output_contract", text)


def reset_output_contract():
    _reset_key("output_contract")


# ----------------------------------------------------------------- panel
def active_panel():
    """The jury panel. Stub mode: one stub juror per persona (offline). Live:
    the cross-product of models x personas (one juror per pairing). Disabled
    personas are skipped (missing flag = enabled); with none enabled, fall
    back to a single neutral juror rather than an empty panel."""
    personas = [p for p in all_personas() if p.get("enabled", True)] \
        or [{"name": "", "temperature": 0.2, "text": ""}]
    if os.getenv("JURY_MODE", "stub").lower() == "stub":
        return [
            jury.JuryMember(f"stub · {p.get('name') or 'neutral'}", "stub", "stub",
                            float(p.get("temperature", 0.2)), p.get("text", ""))
            for p in personas
        ]
    models = [m for m in all_models() if m.get("enabled", True)] \
        or [dict(m) for m in DEFAULT_MODELS]
    members = []
    for m in models:
        for p in personas:
            label = f"{m['provider']}:{m['model']}"
            if p.get("name"):
                label += f" · {p['name']}"
            members.append(jury.JuryMember(label, m["provider"], m["model"],
                                           float(p.get("temperature", 0.2)), p.get("text", "")))
    return members
