from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Any


DEFAULT_MODEL = "deepseek-v4.1-flash-1017"
DEFAULT_PROVIDER = "aliyun"

# Provider metadata is shared by the HTTP settings API and the browser.  Keep
# the defaults deliberately small and stable.  Users can still type any model
# id exposed by a compatible endpoint, while the presets make the common
# cloud and local setups one-click choices.
PROVIDER_ALIASES = {
    "dashscope": "aliyun",
    "alibaba": "aliyun",
    "qwen2": "qwen",
    "qwen3": "qwen",
    "moonshot": "kimi",
    "kimi.ai": "kimi",
    "lm-studio": "lmstudio",
    "lm_studio": "lmstudio",
}

LOCAL_PROVIDER_IDS = frozenset({"ollama", "lmstudio"})

PROVIDER_PRESETS = {
    "aliyun": {
        "label": "阿里云百炼 / Model Studio",
        "base_url": "",
        "models": ["deepseek-v4.1-flash-1017", "deepseek-v4.1-flash", "deepseek-v4-pro"],
        "needs_workspace": True,
        "api_key_required": True,
    },
    "qwen": {
        "label": "通义千问 / Qwen",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-turbo", "qwen-max", "qwen3-max"],
        "needs_workspace": False,
        "api_key_required": True,
    },
    "deepseek": {
        "label": "DeepSeek 官方兼容接口",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "needs_workspace": False,
        "api_key_required": True,
    },
    "kimi": {
        "label": "Moonshot / Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["kimi-k2-turbo-preview", "kimi-k2-thinking", "moonshot-v1-8k", "moonshot-v1-32k"],
        "needs_workspace": False,
        "api_key_required": True,
    },
    "ollama": {
        "label": "本地 Ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "models": ["qwen3:8b", "deepseek-r1:8b", "llama3.2:3b"],
        "needs_workspace": False,
        "api_key_required": False,
        "local": True,
    },
    "lmstudio": {
        "label": "本地 LM Studio",
        "base_url": "http://127.0.0.1:1234/v1",
        "models": ["local-model", "qwen3-8b", "deepseek-r1-8b"],
        "needs_workspace": False,
        "api_key_required": False,
        "local": True,
    },
    "openai": {
        "label": "OpenAI 兼容接口",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o-mini", "gpt-4.1-mini"],
        "needs_workspace": False,
        "api_key_required": True,
    },
    "custom": {
        "label": "自定义 OpenAI-compatible",
        "base_url": "",
        "models": [],
        "needs_workspace": False,
        "api_key_required": True,
    },
}


def canonical_provider(value: str | None) -> str:
    """Return the stable provider id used in persisted settings and APIs."""
    provider = str(value or DEFAULT_PROVIDER).strip().lower()
    return PROVIDER_ALIASES.get(provider, provider)


def provider_needs_api_key(provider: str | None) -> bool:
    provider_id = canonical_provider(provider)
    return bool(PROVIDER_PRESETS.get(provider_id, {}).get("api_key_required", True))


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the selected OpenAI-compatible gateway.

    The browser never receives this object.  In local development the gateway
    defaults to ``mock`` so the UI can run without credentials.
    """

    model: str = DEFAULT_MODEL
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: str = ""
    mode: str = "mock"
    timeout: float = 30.0
    reasoning_effort: str = "low"
    region: str = "cn-beijing"
    workspace_id: str = ""
    max_retries: int = 2
    provider: str = DEFAULT_PROVIDER

    @classmethod
    def from_env(cls) -> "Settings":
        provider = canonical_provider(os.getenv("HUITONG_PROVIDER", DEFAULT_PROVIDER))
        preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["custom"])
        region = os.getenv("DASHSCOPE_REGION", os.getenv("HUITONG_REGION", "cn-beijing"))
        workspace_id = os.getenv("DASHSCOPE_WORKSPACE_ID", os.getenv("HUITONG_WORKSPACE_ID", ""))
        explicit_base = os.getenv("HUITONG_BASE_URL", "")
        if not explicit_base:
            explicit_base = {
                "aliyun": os.getenv("DASHSCOPE_BASE_URL", ""),
                "qwen": os.getenv("QWEN_BASE_URL", os.getenv("DASHSCOPE_BASE_URL", "")),
                "deepseek": os.getenv("DEEPSEEK_BASE_URL", ""),
                "kimi": os.getenv("KIMI_BASE_URL", os.getenv("MOONSHOT_BASE_URL", "")),
                "ollama": os.getenv("OLLAMA_BASE_URL", ""),
                "lmstudio": os.getenv("LMSTUDIO_BASE_URL", os.getenv("LM_STUDIO_BASE_URL", "")),
                "openai": os.getenv("OPENAI_BASE_URL", ""),
            }.get(provider, "")
        if explicit_base:
            base_url = explicit_base.rstrip("/")
        elif workspace_id:
            base_url = f"https://{workspace_id}.{_region_host(region)}.maas.aliyuncs.com/compatible-mode/v1"
        else:
            base_url = str(preset.get("base_url", ""))
            if provider == "aliyun" and not base_url:
                base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        key_env = {
            "aliyun": ("DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY"),
            "qwen": ("QWEN_API_KEY", "DASHSCOPE_API_KEY"),
            "deepseek": ("DEEPSEEK_API_KEY",),
            "kimi": ("KIMI_API_KEY", "MOONSHOT_API_KEY"),
            "openai": ("OPENAI_API_KEY",),
            "custom": ("HUITONG_API_KEY",),
        }.get(provider, ("HUITONG_API_KEY",))
        api_key = next((os.getenv(name, "") for name in key_env if os.getenv(name, "")), "")
        return cls(
            model=os.getenv("HUITONG_MODEL", os.getenv("DASHSCOPE_MODEL", str((preset.get("models") or [DEFAULT_MODEL])[0]))),
            base_url=base_url,
            api_key=api_key,
            mode=os.getenv("HUITONG_GATEWAY_MODE", "mock").lower(),
            timeout=float(os.getenv("HUITONG_TIMEOUT", "30")),
            reasoning_effort=os.getenv("DASHSCOPE_REASONING_EFFORT", os.getenv("HUITONG_REASONING_EFFORT", "low")),
            region=region,
            workspace_id=workspace_id,
            max_retries=max(0, int(os.getenv("HUITONG_MAX_RETRIES", "2"))),
            provider=provider,
        )

    def public_dict(self) -> dict[str, Any]:
        return {"provider": self.provider, "model": self.model, "base_url": self.base_url,
                "mode": self.mode, "timeout": self.timeout, "reasoning_effort": self.reasoning_effort,
                "region": self.region, "workspace_id": self.workspace_id,
                "api_key_configured": bool(self.api_key)}

    @classmethod
    def from_payload(cls, payload: dict[str, Any], current: "Settings | None" = None) -> "Settings":
        base = current or cls.from_env()
        provider = canonical_provider(payload.get("provider", base.provider))
        if provider not in PROVIDER_PRESETS:
            raise ValueError("provider_invalid")
        preset = PROVIDER_PRESETS[provider]
        workspace_id = str(payload.get("workspace_id", base.workspace_id if provider == base.provider else "") or "")
        raw_url = payload.get("base_url")
        url = str(raw_url).strip().rstrip("/") if raw_url else str(preset.get("base_url", ""))
        if provider == "aliyun" and workspace_id and not raw_url:
            url = f"https://{workspace_id}.{_region_host(str(payload.get('region', base.region) or base.region))}.maas.aliyuncs.com/compatible-mode/v1"
        elif provider == "aliyun" and not url:
            url = cls().base_url
        key = payload.get("api_key")
        # Empty or masked keys retain the current server-side secret.
        if (provider in LOCAL_PROVIDER_IDS or provider != base.provider) and key in (None, "", "***", "[configured]"):
            api_key = ""
        else:
            api_key = base.api_key if key in (None, "", "***", "[configured]") else str(key)
        mode = str(payload.get("mode", "live" if (api_key or not provider_needs_api_key(provider)) else "mock")).lower()
        model = str(payload.get("model") or (preset.get("models") or [base.model])[0])
        return replace(base, provider=provider, model=model, base_url=url, api_key=api_key,
                       mode=mode,
                       timeout=float(payload.get("timeout", base.timeout)),
                       reasoning_effort=str(payload.get("reasoning_effort", base.reasoning_effort)),
                       region=str(payload.get("region", base.region)),
                       workspace_id=workspace_id)


def _region_host(region: str) -> str:
    return {
        "cn-beijing": "cn-beijing",
        "ap-southeast-1": "ap-southeast-1",
        "us-east-1": "us-east-1",
        "eu-central-1": "eu-central-1",
        "ap-northeast-1": "ap-northeast-1",
        "cn-hongkong": "cn-hongkong",
    }.get(region, region)
